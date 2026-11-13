#!/usr/bin/env bash
# Install this app as a real ExApp into the HaRP topology from compose.exapp.yml.
#
#   docker compose -f compose.exapp.yml up -d --wait   # 1. topology, waits for healthy
#   bash scripts/bootstrap_exapp.sh                    # 2. AppAPI, daemon, image, ExApp
#   docker compose -f compose.exapp.yml down           # 3. stop, keep the data volume
#
# Step 2 builds the image and pushes it into the local registry itself, so the three
# commands above are the whole installation.
#
# Idempotent by design: every step checks first and skips what already exists, so a second
# run is a no-op apart from a fresh app password in .env.exapp. That file is git-ignored;
# .env.exapp.example documents the variable names.
#
# The development loop without a container image:
#
#   bash scripts/bootstrap_exapp.sh --manual
#
# registers a manual-install daemon and the app with a fixed secret and a fixed port, so a
# locally started `nc-mcp-exapp` process serves the requests and no rebuild is needed per
# iteration. The fixed secret is the point: a re-registration hands out a new one, and a
# process that still holds the old one answers 401 to everything (research pitfall 11).
#
# The public staging instance of plan 03-09:
#
#   bash scripts/bootstrap_exapp.sh --staging
#
# does the same work against compose.staging.yml instead of compose.exapp.yml: the public
# host name from NC_STAGING_DOMAIN becomes the base of NC_MCP_PUBLIC_URL, the connection
# file is .env.staging.app, and the bruteforce guard stays on, because that instance is
# reachable from the internet. It is a flag and not an environment variable on purpose,
# for the same reason COMPOSE_FILE is not overridable (WR-07): a forgotten export in a
# shell must never be able to redirect this script at a topology the caller did not mean.
# scripts/setup_staging.sh is the only intended caller; docs/staging-setup.md is the
# runbook around it.
#
# The Nextcloud 35 evidence instance of docs/nc35-evidence.md:
#
#   export HP_SHARED_KEY="$(openssl rand -hex 32)"
#   docker compose -f compose.nc35.yml up -d --wait
#   bash scripts/bootstrap_exapp.sh --nc35
#
# does the same work against compose.nc35.yml on port 8082, so the 34 topology keeps
# running untouched next to it. It is a flag for the same reason --staging is one: the
# first version of this was a copy of this file with two constants changed, and the three
# it did not change (the port, the HaRP container and the network) made it create accounts
# in the 34 instance while asserting against the 35 one, which looked like a product defect
# for an hour.
#
# This script only ever talks to one of the two throwaway topologies named above. It never
# stops a container of the test topology in this repository and never destroys a volume,
# which is why neither that file name nor a "down" command appears anywhere below.
set -euo pipefail

cd "$(dirname "$0")/.."

# Git Bash rewrites arguments that look like Unix paths before the process sees them, and
# the route regexes and the container paths below are exactly such arguments. No effect on
# Linux, where the variable is simply unknown.
export MSYS_NO_PATHCONV=1

MANUAL_MODE=0
STAGING_MODE=0
NC35_MODE=0
for argument in "$@"; do
  case "${argument}" in
    --manual) MANUAL_MODE=1 ;;
    --staging) STAGING_MODE=1 ;;
    --nc35) NC35_MODE=1 ;;
    *)
      echo "ERROR: unknown argument '${argument}'. Known flags: --manual, --staging, --nc35." >&2
      exit 1
      ;;
  esac
done
if [ $((STAGING_MODE + NC35_MODE)) -gt 1 ]; then
  echo "ERROR: --staging and --nc35 are two different topologies. Pick one." >&2
  exit 1
fi
if [ "${MANUAL_MODE}" -eq 1 ] && [ "${NC35_MODE}" -eq 1 ]; then
  echo "ERROR: --manual serves the app from this host, and the Nextcloud 35 evidence has" >&2
  echo "to run the container image AppAPI deploys. Drop --manual." >&2
  exit 1
fi
if [ "${MANUAL_MODE}" -eq 1 ] && [ "${STAGING_MODE}" -eq 1 ]; then
  echo "ERROR: --manual is the local development loop and --staging is the public" >&2
  echo "instance. Combining them would register a local process as the public ExApp." >&2
  exit 1
fi

# Not overridable, and checked below (WR-07). This script creates users, hands out app
# passwords and, on the local topology, switches `auth.bruteforce.protection.enabled` off.
# All three are fine on a throwaway topology of this repository and unacceptable on any
# other instance, so a forgotten `export COMPOSE_FILE=...` in the calling shell must not be
# able to aim it at the test topology of this repository, which is in daily use. The
# staging topology is selected by the --staging flag above, never by the environment.
COMPOSE_FILE="compose.exapp.yml"
PROJECT_NAME="nc-mcp-exapp"
SERVICE="nextcloud"
HARP_CONTAINER="${HARP_CONTAINER:-nc-mcp-exapp-harp}"
HOST_PORT="${NC_EXAPP_PORT:-8081}"
# The name of the compose network, as written in compose.exapp.yml. The deploy daemon
# attaches the ExApp container to it, which is how HaRP and Nextcloud reach the app.
NETWORK_NAME="${NC_EXAPP_NETWORK:-nc-mcp-exapp-net}"
DAEMON_NAME="harp_proxy_docker"
MANUAL_DAEMON_NAME="manual_install"
APP_ID="mcp_connector"
APP_NAME="MCP Connector"
# Loopback registry from compose.exapp.yml. The Docker daemon of the host treats a
# 127.0.0.1 registry as an allowed insecure one without any extra configuration.
REGISTRY="${NC_EXAPP_REGISTRY:-127.0.0.1:5000}"
IMAGE_NAME="${APP_ID}"
# 23000 to 23999 is the port range the FRP server inside HaRP accepts (allowPorts in its
# frps.toml), and it is the same range AppAPI picks from when a registration carries no
# port. A port outside it is answered with "start error: port not allowed" by frpc, and
# then HAProxy has no backend and every heartbeat is a 503.
APP_PORT="${NC_EXAPP_APP_PORT:-23000}"
MANUAL_APP_PORT="${NC_EXAPP_MANUAL_PORT:-23001}"
# At least ten characters: Nextcloud's password policy rejects anything shorter with
# "Password needs to be at least 10 characters long." and occ exits 1.
ALICE_PASSWORD="${NC_EXAPP_ALICE_PASSWORD:-alice-test-pw-01}"
BOB_PASSWORD="${NC_EXAPP_BOB_PASSWORD:-bob-test-pw-01}"
# The IMAP password of the spike mail account (see ensure_mail_account). Not a Nextcloud
# credential and not subject to the password policy: it belongs to an account on the GreenMail
# service of compose.exapp.yml, which lives in that throwaway topology only and accepts mail
# without authentication anyway. The same variable with the same default is interpolated into
# GREENMAIL_OPTS, so the two places cannot drift apart.
ALICE_IMAP_PASSWORD="${NC_EXAPP_ALICE_IMAP_PASSWORD:-alice-spike-imap-pw}"
# The IMAP and SMTP endpoint of that account. `greenmail` is the service name from
# compose.exapp.yml and therefore the host name inside the network nc-mcp-exapp-net. Both
# values are written out literally rather than composed from parts, so a grep finds them.
MAIL_HOST="greenmail"
MAIL_IMAP_PORT="3143"
MAIL_SMTP_PORT="3025"
TOKEN_NAME="mcp-exapp"
ENV_FILE="${ENV_FILE:-.env.exapp}"
# The base URL a browser and a client use. Everything the app publishes about itself is
# derived from it, so it is one value and not three.
BASE_URL="http://127.0.0.1:${HOST_PORT}"
# The URL AppAPI and the deploy daemon call Nextcloud under. It has to be the same way a
# browser takes, otherwise the heartbeat fails (research pitfall 7).
NC_DAEMON_URL="http://caddy"
# Extra arguments every `docker compose` call of this script carries. Empty for the local
# topology, which needs no environment file; the staging topology interpolates mandatory
# variables and would refuse every command without one.
COMPOSE_ENV_ARGS=()
# Disabling the bruteforce guard is a property of an unreachable instance, never of a
# public one. The staging branch below turns this off.
DISABLE_BRUTEFORCE=1

if [ "${NC35_MODE}" -eq 1 ]; then
  # The Nextcloud 35 evidence instance. Same script, same steps, five differences, and all
  # five have to move together: another compose file, another project, another HaRP
  # container, another network and another port. Leaving any one of them on the 34 value
  # points half of this script at the other instance, which is exactly what the first,
  # copied version of this branch did.
  COMPOSE_FILE="compose.nc35.yml"
  PROJECT_NAME="nc-mcp-nc35"
  HARP_CONTAINER="nc35-harp"
  NETWORK_NAME="nc-mcp-nc35-net"
  ENV_FILE="${ENV_FILE_NC35:-.env.nc35}"
  HOST_PORT="${NC_NC35_PORT:-8082}"
  BASE_URL="http://127.0.0.1:${HOST_PORT}"
fi

if [ "${STAGING_MODE}" -eq 1 ]; then
  # The public instance of plan 03-09. Same script, same steps, four differences: another
  # compose file, another project, the public host name in every URL, and a bruteforce
  # guard that stays where it is.
  COMPOSE_FILE="compose.staging.yml"
  PROJECT_NAME="nc-mcp-staging"
  HARP_CONTAINER="nc-mcp-staging-harp"
  NETWORK_NAME="nc-mcp-staging-net"
  ENV_FILE="${ENV_FILE_STAGING:-.env.staging.app}"
  COMPOSE_ENV_ARGS=(--env-file "${NC_STAGING_ENV_FILE:-.env.staging}")
  DISABLE_BRUTEFORCE=0
  # The one value the whole staging run hangs on. It is interpolated into the URLs the app
  # publishes about itself, so its shape is checked before it is used (see
  # require_host_name, called from the run block at the end).
  STAGING_DOMAIN="${NC_STAGING_DOMAIN:?set NC_STAGING_DOMAIN to the public host name, see docs/staging-setup.md}"
  BASE_URL="https://${STAGING_DOMAIN}"
  NC_DAEMON_URL="https://${STAGING_DOMAIN}"
  # The two throwaway accounts of a public instance get generated passwords, not the
  # documented ones. scripts/setup_staging.sh generates them into .env.staging and exports
  # them; the fallbacks below are refused by require_generated_password.
  ALICE_PASSWORD="${NC_EXAPP_ALICE_PASSWORD:-}"
  BOB_PASSWORD="${NC_EXAPP_BOB_PASSWORD:-}"
fi

# The address this app is reachable under from the outside, which is also the issuer of
# its authorization server and the resource of its protected resource document. It is
# handed to the container at registration time (see register_exapp) and it is the one
# value an administrator has to get right for OAuth (docs/oauth-setup.md). On the staging
# instance it must be the public URL: plan 03-08 measured what happens without it, namely
# a discovery document that names 127.0.0.1 and a client that cannot connect at all.
PUBLIC_URL="${NC_EXAPP_PUBLIC_URL:-${BASE_URL}/exapps/${APP_ID}}"
# Filled by ensure_image and read by verify_image_digest right before the registration.
IMAGE_DIGEST=""

ensure_own_topology() {
  if [ ! -f "${COMPOSE_FILE}" ]; then
    echo "ERROR: ${COMPOSE_FILE} is not here. Run this script from the repository root." >&2
    return 1
  fi
  if ! grep -q "^name: ${PROJECT_NAME}\$" "${COMPOSE_FILE}"; then
    echo "ERROR: ${COMPOSE_FILE} does not declare the ${PROJECT_NAME} project." >&2
    echo "This script only ever runs against a throwaway topology (WR-07)." >&2
    return 1
  fi
}

# A host name lands unquoted in URLs, in a registration payload and in the compose
# interpolation, so its shape is pinned before any of that happens (IN-07). Letters,
# digits, dots and hyphens, at least one dot: anything else is a typo or an injection.
require_host_name() {
  local value="$1"
  if ! printf '%s' "$value" | grep -E '^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}$' >/dev/null; then
    echo "ERROR: NC_STAGING_DOMAIN is '${value}', which is not a host name." >&2
    echo "It is interpolated into every URL this app publishes about itself. Refusing." >&2
    return 1
  fi
}

# On a public instance the account passwords are the only thing between the internet and
# two accounts that hold test data, and the documented defaults of the local topology are
# published in this repository. Twenty characters is what `openssl rand -hex 16` produces.
require_generated_password() {
  local name="$1" value="$2"
  if [ "${#value}" -lt 20 ]; then
    echo "ERROR: ${name} is empty or shorter than 20 characters." >&2
    echo "The staging instance is reachable from the internet, so its accounts do not use" >&2
    echo "the documented test passwords. scripts/setup_staging.sh generates them." >&2
    return 1
  fi
}

# One place that knows how this script talks to its topology. Every compose call goes
# through it, so the staging environment file can never be forgotten on one of them.
dc() {
  docker compose "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" "$@"
}

# The command a reader has to type to look at the same thing this script looked at.
compose_hint() {
  printf 'docker compose %s-f %s' "${COMPOSE_ENV_ARGS[*]:+${COMPOSE_ENV_ARGS[*]} }" "${COMPOSE_FILE}"
}

occ() {
  dc exec -T --user www-data "${SERVICE}" php occ "$@"
}

# Every secret this script hands to the container travels through stdin, never through a
# command line (WR-06). The argv of `docker` is world readable in `ps aux` for the whole
# duration of a call, and an inline -e assignment additionally lands in the container
# config of the exec. A pipe is private to the two processes at its ends.
#
# The `sh -c '<snippet>' sh "$@"` form is the portable way to give that snippet positional
# arguments: the word after the snippet becomes $0, everything after it becomes $1 and up.
occ_stdin() {
  local snippet="$1"
  shift
  dc exec -T --user www-data "${SERVICE}" \
    sh -c "${snippet}" sh "$@"
}

# A password for occ has to travel inside the container: an exported variable on the host
# never reaches the process that `docker compose exec` starts.
occ_pw() {
  local password="$1"
  shift
  printf '%s' "$password" |
    occ_stdin 'OC_PASS="$(cat)"; export OC_PASS; exec php occ "$@"' "$@"
}

# grep on a pipe never uses -q here: with pipefail, -q exits on the first match, the pipe
# closes early and the writing side of the pipe can die on SIGPIPE (exit 141), which turns
# a successful check into a flaky bootstrap failure (two CI runs died with the calendar
# visibly printed one line above the failing check). grep without -q reads its input to
# the end; the match result goes to /dev/null instead.
#
# The rule reads "on a pipe" and no longer "on an occ pipe" (IN-05). The validators below
# pipe a printf into grep, where the writer finishes before grep could ever close anything,
# so they were an exception nobody had written down, spelled -Eq, and the test that holds
# this rule did not see them. One rule for every pipe is cheaper to keep than an exception
# that has to be recognised again in every review; the gate is
# test_no_grep_q_on_a_pipe_in_the_shell_scripts.
wait_for_install() {
  local attempt
  for attempt in $(seq 1 60); do
    if occ status 2>/dev/null | grep "installed: true" >/dev/null; then
      echo "nextcloud: installed"
      return 0
    fi
    echo "waiting for the Nextcloud installation to finish (${attempt}/60)"
    sleep 5
  done
  echo "ERROR: Nextcloud is still not installed after five minutes." >&2
  echo "Check: $(compose_hint) logs --tail=100 ${SERVICE}" >&2
  return 1
}

ensure_app() {
  local app="$1" output
  if output="$(occ app:install "$app" 2>&1)"; then
    echo "app ${app}: installed"
    return 0
  fi
  if output="$(occ app:enable "$app" 2>&1)"; then
    echo "app ${app}: enabled"
    return 0
  fi
  echo "ERROR: could not install or enable ${app}:" >&2
  echo "${output}" >&2
  echo "See the FALLBACK block at the end of this script." >&2
  return 1
}

ensure_user() {
  local uid="$1" password="$2" output
  if occ user:info "$uid" >/dev/null 2>&1; then
    echo "user ${uid}: exists"
    return 0
  fi
  # occ reports a rejected password on stdout, so the output is captured and only shown
  # when it matters. Swallowing it would turn a policy violation into a silent exit 1.
  if ! output="$(occ_pw "$password" user:add --password-from-env "$uid" 2>&1)"; then
    echo "ERROR: could not create user ${uid}:" >&2
    echo "${output}" >&2
    return 1
  fi
  echo "user ${uid}: created"
}

# The host and the port are parameters, and the topology now carries a server that answers
# under them. Until plan 10-01 the account pointed at a host that does not resolve, which was
# enough for MAIL-04 (the question there was whether an impersonated request reaches Mail's own
# controllers, and a 500 out of a failed IMAP sync answers it as well as a 200). It is not
# enough for phase 10: `specialRole`, `previewText`, the filter grammar and the length of a
# converted HTML body are properties of real messages, and a tool built on guessed shapes would
# only be measured in the live run at the end of the phase.
#
# `imapSslMode` and `smtpSslMode` are `none` because GreenMail inside the compose network holds
# no certificate. That is a property of this throwaway topology and never a recommendation.
#
# The IMAP password travels on the command line, which WR-06 forbids for every value that
# carries authority. This one carries none: it belongs to a mailbox on a service that runs in
# this throwaway topology only, keeps everything in memory, accepts mail without any
# authentication and is not reachable from outside the compose network. The occ command takes
# the password as a positional argument and has no stdin form.
#
# The account id of the account this function leaves behind, for the sync and the delivery
# step below. A function cannot return a string in shell, and echoing it would mix into the
# progress output every other ensure_* function writes.
MAIL_ACCOUNT_ID=""

# One line "<account-id> <imap-host>:<imap-port>" for the account of `uid` that carries
# `email`, or nothing. `mail:account:export` prints a block per account:
#
#   Account 1:
#   - E-Mail: alice@example.test
#   ...
#   - IMAP host: greenmail:3143, security: none
#
# awk is fed the whole output and prints at END instead of exiting at the first match: an
# early exit closes the pipe and can kill the writing occ with SIGPIPE, which is the same
# failure mode the grep rule above this file's helpers describes.
mail_account_row() {
  local uid="$1" email="$2"
  occ mail:account:export "$uid" 2>/dev/null | tr -d '\r' | awk -v want="$email" '
    /^Account [0-9]+:/ { id = $2; sub(/:$/, "", id); mail = "" }
    /^- E-Mail: / { mail = $3 }
    /^- IMAP host: / {
      if (mail == want && found == "") { host = $4; sub(/,$/, "", host); found = id " " host }
    }
    END { if (found != "") print found }
  '
}

ensure_mail_account() {
  local uid="$1" name="$2" email="$3" password="$4" host="$5" port="$6"
  local output row account_id endpoint
  # `mail:account:export` exits 0 for a user without any account and prints nothing, so the
  # output decides and not the exit code. Without this check a second run would create a
  # second account for the same address.
  #
  # The address alone is not enough any more, and that is the point of this check (T-10-03):
  # an account left behind by an earlier run still points at the host that never answers, a
  # match on the address alone would report "exists", the bootstrap would end green and not a
  # single IMAP fetch would be possible. So the endpoint has to match as well, and an account
  # on the wrong one is deleted and created again. `occ mail:account:delete <account-id>`
  # exists in Mail 5.11.1 (verified with `occ list mail` on the running instance, 2026-08-24);
  # should a future version drop it, the error path below names the one manual step instead of
  # walking on silently.
  row="$(mail_account_row "$uid" "$email")"
  if [ -n "$row" ]; then
    account_id="${row%% *}"
    endpoint="${row#* }"
    if [ "$endpoint" = "${host}:${port}" ]; then
      echo "mail account ${uid}: exists on ${endpoint} (id ${account_id})"
      MAIL_ACCOUNT_ID="${account_id}"
      return 0
    fi
    echo "mail account ${uid}: points at ${endpoint}, expected ${host}:${port}, recreating"
    if ! output="$(occ mail:account:delete "${account_id}" 2>&1)"; then
      echo "ERROR: the mail account of ${uid} points at ${endpoint} and could not be deleted:" >&2
      echo "${output}" >&2
      echo "delete the mail account of alice in the Mail app once, then run this script again" >&2
      return 1
    fi
    echo "mail account ${uid}: deleted the account on ${endpoint}"
  fi
  # Same reason as in ensure_user: occ reports a refused value on stdout, and swallowing it
  # would turn a rejected account into a silent exit 1.
  if ! output="$(occ mail:account:create-imap "$uid" "$name" "$email" \
    "$host" "$port" none "$uid" "$password" \
    "$host" "${MAIL_SMTP_PORT}" none "$uid" "$password" password 2>&1)"; then
    echo "ERROR: could not create the spike mail account for ${uid}:" >&2
    echo "${output}" >&2
    return 1
  fi
  row="$(mail_account_row "$uid" "$email")"
  if [ -z "$row" ]; then
    echo "ERROR: the mail account of ${uid} was created but does not show up in the export." >&2
    return 1
  fi
  MAIL_ACCOUNT_ID="${row%% *}"
  echo "mail account ${uid}: created on ${host}:${port} (id ${MAIL_ACCOUNT_ID})"
}

# The number of test mails plan 10-01 delivers. Six messages across the five purposes that
# document calls for, because the subject purpose needs two of them (`Rechnung` and
# `Rechnung Mai`, the pair that shows what the space rule of the filter grammar does).
MAIL_FIXTURE_COUNT=6

# The test mails of plan 10-01. They exist so that four assumptions of 10-RESEARCH.md become
# measurements: the value set of `specialRole` (A1), whether and how long `previewText` is
# filled (A2), the byte length of a converted HTML body (A3) and the behaviour of the filter
# grammar against real messages (A4).
#
# Every sender lives under example.test and every content is invented. That is what makes the
# stage 2 protocol in docs/spike-mail.md allowed to print field values, unlike the phase 8
# measurement whose account answer carried a real address and was therefore cut to 120
# characters (T-08-01).
#
# The delivery runs from a throwaway container inside the compose network, because GreenMail
# has no published port (T-10-01) and the host therefore cannot reach it at all. The image is
# pinned (T-10-SC) and nothing is installed into it: smtplib, imaplib and email are standard
# library. The script travels through stdin rather than through `python -c`, so neither it nor
# the mailbox password appears in the world readable argv of the docker client (WR-06); the
# password is handed over as a name with `-e MAIL_PW`, which copies the value out of the
# environment of this process.
#
# Idempotent through the mailbox itself and not through a marker file: the function counts the
# messages in the INBOX over IMAP first and delivers nothing when they are already there. A
# marker file in the Nextcloud volume would claim something about a state that lives in
# GreenMail, and GreenMail keeps everything in memory: a restart of that container empties the
# mailbox while the marker would still be sitting in the volume.
deliver_test_mail() {
  local uid="$1" address="$2" password="$3"
  if [ "${STAGING_MODE}" -eq 1 ]; then
    # The public topology of compose.staging.yml carries no GreenMail service, and it must not
    # grow one: it is reachable from the internet. The mail account there stays a row without
    # a server behind it, exactly as it was before plan 10-01.
    echo "test mails ${uid}: skipped (the staging topology carries no mail server)"
    return 0
  fi
  MAIL_PW="${password}" \
  MAIL_HOST="${MAIL_HOST}" \
  MAIL_SMTP_PORT="${MAIL_SMTP_PORT}" \
  MAIL_IMAP_PORT="${MAIL_IMAP_PORT}" \
  MAIL_USER="${uid}" \
  MAIL_ADDRESS="${address}" \
  MAIL_EXPECTED="${MAIL_FIXTURE_COUNT}" \
  docker run --rm -i --network "${NETWORK_NAME}" \
    -e MAIL_PW -e MAIL_HOST -e MAIL_SMTP_PORT -e MAIL_IMAP_PORT \
    -e MAIL_USER -e MAIL_ADDRESS -e MAIL_EXPECTED \
    python:3.13-alpine python - <<'PY'
import imaplib
import os
import smtplib
import sys
import time
from email.message import EmailMessage
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

HOST = os.environ["MAIL_HOST"]
SMTP_PORT = int(os.environ["MAIL_SMTP_PORT"])
IMAP_PORT = int(os.environ["MAIL_IMAP_PORT"])
USER = os.environ["MAIL_USER"]
PASSWORD = os.environ["MAIL_PW"]
ADDRESS = os.environ["MAIL_ADDRESS"]
EXPECTED = int(os.environ["MAIL_EXPECTED"])


def imap():
    """One IMAP connection, retried: the service has no healthcheck to wait on."""
    last = None
    for _ in range(30):
        try:
            box = imaplib.IMAP4(HOST, IMAP_PORT)
        except OSError as error:
            last = error
            time.sleep(2)
            continue
        box.login(USER, PASSWORD)
        return box
    raise SystemExit(f"greenmail did not answer on {HOST}:{IMAP_PORT}: {last}")


def inbox_count():
    box = imap()
    try:
        status, data = box.select("INBOX")
        if status != "OK":
            raise SystemExit(f"selecting INBOX answered {status}: {data}")
        return int(data[0])
    finally:
        box.logout()


def block(index):
    return (
        "<table><tr><td><table><tr><td>"
        f"<p>Angebot {index}: Ma&szlig;e, Gr&uuml;&szlig;e und Preise</p>"
        f"<div>Beschreibung {index} mit <b>Auszeichnung</b> und einem Verweis auf "
        f'<a href="https://example.test/angebot/{index}">Angebot {index}</a>.<br>'
        "Eine zweite Zeile, damit der Block die L&auml;nge eines echten "
        "Newsletter-Abschnitts bekommt und die Wandlung etwas zu tun hat.</div>"
        f"<ul><li>Punkt A {index}</li><li>Punkt B {index}</li>"
        f"<li>Punkt C {index}</li></ul>"
        "</td></tr></table></td></tr></table>"
    )


def newsletter(target_bytes):
    parts = []
    total = 0
    index = 0
    while total < target_bytes:
        piece = block(index)
        parts.append(piece)
        total += len(piece)
        index += 1
    return (
        "<html><head>"
        "<style>body{font-family:sans-serif;color:#333}"
        "table{border-collapse:collapse;width:100%}td{padding:4px}</style>"
        "<script>var tracking = 1; function noop(){return tracking;}</script>"
        "</head><body><h1>Newsletter der Beispiel GmbH</h1>"
        + "".join(parts)
        + "<p>Abmelden: <a href=\"https://example.test/abmelden\">hier</a></p>"
        "</body></html>"
    )


def plain(sender, subject, body):
    # One text/plain part and nothing else, but wrapped in a multipart/mixed envelope, and
    # that wrapping is a workaround and not a preference. GreenMail 2.1.12 casts the content
    # of every message to MimeMultipart in FetchCommand.handleBodyFetch, so a message whose
    # content is a plain String makes the IMAP FETCH fail with a ClassCastException, and
    # Nextcloud answers the full text route with 500 "Could not connect to IMAP server"
    # (measured on 2026-08-24, the stack trace is in the log of nc-mcp-exapp-greenmail).
    # A single part envelope keeps the property this mail exists for: no HTML anywhere in it,
    # so the body of the full text route proves correction K2 all the same.
    message = MIMEMultipart("mixed")
    message["From"] = sender
    message["To"] = ADDRESS
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=False)
    message.attach(MIMEText(body, "plain", "utf-8"))
    return message


def html_mail(sender, subject, html):
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ADDRESS
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=False)
    message.set_content("Dieser Newsletter braucht einen HTML-faehigen Client.")
    message.add_alternative(html, subtype="html")
    return message


def attachment_only(sender, subject):
    # No text part at all, on purpose: the full text route has to be measured against a
    # message whose body is missing (falle 5 of 10-RESEARCH.md).
    message = MIMEMultipart()
    message["From"] = sender
    message["To"] = ADDRESS
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=False)
    part = MIMEApplication(b"Notiz ohne Nachrichtentext.\n", Name="notiz.txt")
    part["Content-Disposition"] = 'attachment; filename="notiz.txt"'
    message.attach(part)
    return message


present = inbox_count()
if present >= EXPECTED:
    print(f"test mails {USER}: already there ({present} in INBOX)")
    sys.exit(0)

messages = [
    # 1. Purely textual, with real umlauts in the subject and in the body. It carries the
    #    evidence for correction K2: the body of the full text route arrives as HTML anyway.
    plain(
        "buero@example.test",
        "Gruesse aus Hamburg, die Masse stehen unten",
        # The link, the ampersand and the angle bracket are the point of this body and not
        # decoration: Html::convertLinks runs UrlLinker plus HTMLPurifier over the text of
        # every message, so exactly these three characters show whether the body of the full
        # text route arrives as HTML even for a message that carries none (K2). A text without
        # them would arrive unchanged and would prove nothing.
        "Moin,\n\nGrüße aus Hamburg. Die Maße des Regals sind 80 x 200 cm.\n"
        "Der Preis liegt bei 30 Euro & Versand, die Straße kennst du ja.\n"
        "Details: https://example.test/regal?groesse=80x200\n"
        "Ein spitzes Zeichen: 5 < 7.\n\nViele Grüße\nDas Büro\n",
    ),
    # 2. A newsletter in a realistic size, the message the byte cap of the full text is
    #    decided on (A3).
    html_mail("newsletter@example.test", "Newsletter August", newsletter(45000)),
    # 3. The upper bound case.
    html_mail("newsletter@example.test", "Grosser Newsletter August", newsletter(400000)),
    # 4a and 4b. The subject filter and the space rule of the filter grammar.
    plain(
        "buchhaltung@example.test",
        "Rechnung",
        "Anbei die Rechnung des laufenden Monats.\n",
    ),
    plain(
        "buchhaltung@example.test",
        "Rechnung Mai",
        "Anbei die Rechnung für den Monat Mai.\n",
    ),
    # 5. No body, one small attachment.
    attachment_only("ablage@example.test", "Nur ein Anhang"),
]

with smtplib.SMTP(HOST, SMTP_PORT, timeout=30) as smtp:
    for message in messages:
        smtp.send_message(message, from_addr=message["From"], to_addrs=[ADDRESS])
print(f"test mails {USER}: delivered {len(messages)} over {HOST}:{SMTP_PORT}")

# One IMAP keyword, so the tags: run of the filter grammar has something to find. Mail maps
# its tags onto IMAP keywords, and $label1 is the first of the default ones. A server that
# refuses user flags is a measurement too, so the refusal is reported and not fatal.
box = imap()
try:
    box.select("INBOX")
    status, data = box.search(None, 'SUBJECT', '"Rechnung"')
    numbers = data[0].split() if status == "OK" and data and data[0] else []
    if numbers:
        status, data = box.store(numbers[0], "+FLAGS", "$label1")
        print(f"test mails {USER}: keyword $label1 on message {numbers[0].decode()}: {status}")
    else:
        print(f"test mails {USER}: no message found to carry a keyword")
finally:
    box.logout()
PY
}

# Without this the messages sit in GreenMail and nowhere else: `listMessages` reads the
# database of the Mail app, and `MailSearch::findMessages` raises MailboxNotCachedException for
# a mailbox that has never been synchronised, which surfaces as a 500 (K6). A measurement
# without this step would read the error path instead of the field shapes.
sync_mail_account() {
  local uid="$1" output
  if [ "${STAGING_MODE}" -eq 1 ]; then
    echo "mail sync ${uid}: skipped (the staging topology carries no mail server)"
    return 0
  fi
  if [ -z "${MAIL_ACCOUNT_ID}" ]; then
    echo "ERROR: no mail account id for ${uid}, so nothing can be synchronised." >&2
    return 1
  fi
  if ! output="$(occ mail:account:sync "${MAIL_ACCOUNT_ID}" -f 2>&1)"; then
    echo "ERROR: could not synchronise the mail account ${MAIL_ACCOUNT_ID} of ${uid}:" >&2
    echo "${output}" >&2
    return 1
  fi
  echo "mail sync ${uid}: account ${MAIL_ACCOUNT_ID} synchronised"
}

# Mandatory, not cosmetic: Nextcloud creates the default calendar and the default address
# book in the listener for UserFirstTimeLoggedInEvent, and `occ user:add` never fires that
# event. Without the two commands below a freshly created test user has no calendar and no
# address book at all, and every CalDAV or CardDAV test fails with an empty result that
# looks like a bug in our own XML (research pitfall 3).
ensure_calendar() {
  local uid="$1" name="$2" attempt
  # The create races the DAV app warming up right after the install, and a create that
  # failed transiently must not pass as "already there": two CI runs died exactly like
  # that, with the rerun green. So the create is retried until the calendar is actually
  # listed, with a hard timeout instead of a single check.
  for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
    occ dav:create-calendar "$uid" "$name" >/dev/null 2>&1 || true
    if occ dav:list-calendars "$uid" 2>/dev/null | grep "$name" >/dev/null; then
      echo "calendar ${uid}/${name}: present (attempt ${attempt})"
      return 0
    fi
    sleep 5
  done
  echo "ERROR: calendar ${uid}/${name} did not appear within 60s." >&2
  return 1
}

ensure_addressbook() {
  local uid="$1" name="$2"
  if occ dav:create-addressbook "$uid" "$name" >/dev/null 2>&1; then
    echo "addressbook ${uid}/${name}: created"
  else
    echo "addressbook ${uid}/${name}: already there"
  fi
}

# Same class of issue as the calendar and address book above: `occ user:add` never fires the
# first login, so a fresh user gets none of the skeleton files a real first login lays down
# and its files home stays completely empty. An empty home has no searchable root node, so a
# WebDAV SEARCH against it raises OCP\Files\NotFoundException on /<uid>/files inside the
# FileSearchBackend and surfaces as HTTP 500, not a clean empty result. A CalDAV or CardDAV
# read still answers empty, which is why only the file search is affected. The permission
# tests search bob's home before bob ever writes to it, so without this a leak test would
# fail on a server error rather than prove the boundary.
#
# Placing one neutral file (exactly what a first login's skeleton would leave behind) and
# scanning it registers the root the search backend looks up, after which SEARCH answers an
# honest empty. The file is generic and never matches the unique markers the permission tests
# search for, so it does not weaken any positive control or leak test. A plain scan alone is
# not enough: an empty home stays unsearchable. Verified against a clean rebuild from wiped
# volumes.
ensure_files_home() {
  local uid="$1"
  dc exec -T --user www-data "${SERVICE}" sh -c \
    "mkdir -p 'data/${uid}/files' && printf 'Initialised by scripts/bootstrap_exapp.sh.\n' \
      > 'data/${uid}/files/Readme.md'"
  if occ files:scan "$uid" >/dev/null 2>&1; then
    echo "files home ${uid}: initialised"
  else
    echo "files home ${uid}: scan failed" >&2
    return 1
  fi
}

# --- the third data layer: a read-only share (plan 05-03) ---------------------------
#
# alice and bob alone can only prove a leak: bob does not see what alice has. Success
# criterion 3 of this phase also asks what bob DOES see, and where Nextcloud stops him
# anyway, and both need an asymmetry that lives in the data rather than in the comparison
# (05-RESEARCH.md, pitfall 6):
#
#   * a folder of alice, shared with bob read-only, with one marked file in it, and
#   * a second marked file of alice that is never shared with anybody.
#
# Then five statements are measurable and none of them is a tautology: bob finds the shared
# file, he does not find the private one, he reads the shared one, he cannot write into the
# read-only folder although our upload tool is create-only, and a second upload on a path
# that exists is refused. The fourth is where permission parity and the create-only promise
# meet at a boundary Nextcloud draws and we do not.
#
# Everything below is created over WebDAV and OCS with alice's own account password, never
# by writing into the data directory the way ensure_files_home has to: a file placed there
# carries no file id until the next files:scan, and a folder without a file id cannot be
# shared at all.

# The unique suffix every name of the fixture carries, pinned across runs exactly like
# APP_SECRET and for a comparable reason: a fresh suffix on a second run would leave the
# instance with a second folder and a second share, and the test would then measure whichever
# of them the current .env.exapp happens to name. Ten hex characters, so a marker can never
# collide with the neutral skeleton file ensure_files_home leaves behind.
share_suffix() {
  local existing=""
  if [ -f "${ENV_FILE}" ]; then
    # With or without the leading slash: the connection file writes the relative spelling
    # (see the heredoc at the end of this script), and a file left behind by an earlier run
    # still carries the absolute one. Accepting both keeps that run's objects in use.
    existing="$(sed -n 's|^NC_MCP_TEST_SHARED_DIR=/\{0,1\}mcp-share-||p' "${ENV_FILE}" |
      head -n1 | tr -d '\r')"
  fi
  if printf '%s' "$existing" | grep -E '^[0-9a-f]{10}$' >/dev/null; then
    printf '%s' "$existing"
    return 0
  fi
  openssl rand -hex 5
}

dav_url() {
  printf '%s/remote.php/dav/files/%s%s' "${BASE_URL}" "$1" "$2"
}

# One authenticated request, with the HTTP status as its only output. The password travels
# through a curl config file on stdin (WR-06): `-u user:password` would sit in the world
# readable argv of curl for the whole duration of every request, and a temporary file would
# have to be cleaned up on every exit path. A failed connection prints 000 and never stops
# the caller, because every caller here decides on the status code itself.
#
# The body is read and dropped instead of being sent to `-o /dev/null`: this script exports
# MSYS_NO_PATHCONV=1 for the route regexes, and with it Git Bash hands curl the literal path
# /dev/null, which does not exist on Windows. curl then fails every such request with
# "curl: (23) client returned ERROR on write" although the answer arrived intact. Measured on
# this host; a status appended to the body works the same way on both platforms.
nc_status() {
  local user="$1" password="$2" method="$3" url="$4" answer status
  shift 4
  answer="$(printf 'user = "%s:%s"\n' "$user" "$password" |
    curl -sS --config - -w '\n%{http_code}' -X "$method" "$@" "$url" || true)"
  status="$(printf '%s' "$answer" | tail -n1 | tr -d '[:space:]')"
  printf '%s' "${status:-000}"
}

# Same request, but the body instead of the status: the share proof reads the answer.
nc_body() {
  local user="$1" password="$2" method="$3" url="$4"
  shift 4
  printf 'user = "%s:%s"\n' "$user" "$password" |
    curl -sS --config - -X "$method" "$@" "$url" || true
}

# Create-only, deliberately: a second run must not overwrite the file whose content the
# parity test asserts, and 412 is Nextcloud saying the file is already exactly where it
# belongs. The marker is written into the content as well as into the name, so a read that
# returns an empty body cannot pass for a successful read.
put_marked_file() {
  local user="$1" password="$2" path="$3" marker="$4" status
  status="$(nc_status "$user" "$password" PUT "$(dav_url "$user" "$path")" \
    -H "If-None-Match: *" -H "Content-Type: text/markdown" \
    --data-binary "# ${marker} (fixture of scripts/bootstrap_exapp.sh, plan 05-03)")"
  case "$status" in
    201 | 204)
      echo "file ${user}${path}: created"
      ;;
    412)
      echo "file ${user}${path}: already there"
      ;;
    *)
      echo "ERROR: PUT ${path} as ${user} answered ${status}." >&2
      return 1
      ;;
  esac
}

# permissions=1 is exactly read (1 read, 2 update, 4 create, 8 delete, 16 reshare). Any
# higher value would take the meaning out of the upload refusal the parity test measures,
# which is why the unit gate in tests/unit/test_exapp_env_setup.py pins this literal.
#
# The status is printed instead of the answer body: OCS v2 maps its own status code onto the
# HTTP one, so 200 is a created share and anything else is worth reading in the log. Letting
# curl discard the body with -o also keeps it from writing into a redirected stdout, which is
# where the first run of this fixture produced a "curl: (23)" line next to a share that had
# in fact been created.
create_readonly_share() {
  local owner="$1" password="$2" recipient="$3" status
  status="$(nc_status "$owner" "$password" POST \
    "${BASE_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares" \
    -H "OCS-APIRequest: true" -H "Accept: application/json" \
    -d "path=${SHARED_DIR}" \
    -d "shareType=0" \
    -d "shareWith=${recipient}" \
    -d "permissions=1")"
  echo "share ${SHARED_DIR} to ${recipient}: create answered ${status}"
}

# Proof instead of assumption, the same rule ensure_calendar follows: the share counts as
# present only when the API lists exactly one share of that folder, it names the recipient,
# and its permission value is 1. A create that failed transiently must never pass as
# "already there", and a share that silently carries write permission must never pass at all.
share_is_readonly_for() {
  local owner="$1" password="$2" recipient="$3" body recipients permissions
  body="$(nc_body "$owner" "$password" GET \
    "${BASE_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares?path=${SHARED_DIR}" \
    -H "OCS-APIRequest: true" -H "Accept: application/json")"
  recipients="$(printf '%s' "$body" | grep -o '"share_with":"[^"]*"' | sort -u || true)"
  permissions="$(printf '%s' "$body" | grep -o '"permissions":[0-9]*' | sort -u || true)"
  [ "$recipients" = "\"share_with\":\"${recipient}\"" ] &&
    [ "$permissions" = '"permissions":1' ]
}

ensure_readonly_share() {
  local owner="$1" owner_password="$2" recipient="$3" recipient_password="$4"
  local status attempt propfind
  status="$(nc_status "$owner" "$owner_password" MKCOL "$(dav_url "$owner" "${SHARED_DIR}")")"
  case "$status" in
    201)
      echo "share folder ${SHARED_DIR}: created"
      ;;
    405)
      echo "share folder ${SHARED_DIR}: already there"
      ;;
    *)
      echo "ERROR: MKCOL ${SHARED_DIR} as ${owner} answered ${status}." >&2
      echo "Is the topology up and reachable under ${BASE_URL}?" >&2
      return 1
      ;;
  esac
  put_marked_file "$owner" "$owner_password" "${SHARED_FILE}" "${SHARED_MARKER}" || return 1
  put_marked_file "$owner" "$owner_password" "${PRIVATE_FILE}" "${PRIVATE_MARKER}" || return 1

  # Without this the share waits in bob's "pending shares" and his home does not carry the
  # folder at all, so every statement about it would measure the missing acceptance step
  # instead of the permission boundary.
  occ config:app:set core shareapi_auto_accept_share --value=yes >/dev/null
  echo "share auto accept: on (test instance)"

  # Same shape as ensure_calendar: retry the create until both proofs stand, with a hard
  # timeout instead of a single look.
  for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
    if share_is_readonly_for "$owner" "$owner_password" "$recipient"; then
      propfind="$(nc_status "$recipient" "$recipient_password" PROPFIND \
        "$(dav_url "$recipient" "${SHARED_DIR}")" -H "Depth: 0")"
      if [ "$propfind" = "207" ]; then
        echo "read-only share ${SHARED_DIR} to ${recipient}: present (attempt ${attempt})"
        return 0
      fi
    else
      create_readonly_share "$owner" "$owner_password" "$recipient" || true
    fi
    sleep 5
  done
  echo "ERROR: ${owner} could not share ${SHARED_DIR} read-only with ${recipient} in 60s." >&2
  echo "Check the shares of that folder: ${BASE_URL}/apps/files" >&2
  return 1
}

# --- the Talk test conversations (plan 09-05) -----------------------------------------
#
# Two conversations of alice, both with real umlauts in the name: one writable and one write
# protected. The write protected one carries the negative case of TALK-03, because a refusal
# with a sentence and a next step needs an object to be refused on and not an assumption.
#
# The changelog conversation (type 4) is deliberately not created and never used as a target.
# Talk creates it for every account by itself, it is always write protected, and it is exactly
# the trap `tools.talk._may_send` catches.
#
# `occ talk:room:create` is **not** idempotent: a second call creates a second room with the
# same name. The room is therefore looked up by name first and only created when it is
# missing. The lookup goes over the conversation list of the account itself, because the app
# ships no listing command at all: measured against spreed 24.0.4 on 2026-08-21, the `talk:`
# namespace offers create, update, delete, add, remove, promote and demote, and nothing that
# lists rooms.
#
# The name is matched on its ASCII prefix and not on the whole string, and that is not
# laziness: PHP writes every umlaut of a JSON answer as a \uXXXX escape, so a grep for the
# literal name would never match the answer of the API. The prefix is unique per
# conversation, which is what keeps the match exact enough.
talk_room_token() {
  local uid="$1" password="$2" key="$3"
  nc_body "$uid" "$password" GET "${BASE_URL}/ocs/v2.php/apps/spreed/api/v4/room" \
    -H "OCS-APIRequest: true" -H "Accept: application/json" |
    tr '{' '\n' | grep "\"displayName\":\"${key}" |
    grep -o '"token":"[a-z0-9]\{4,30\}"' | head -n1 | sed 's/.*:"//; s/"$//' || true
}

ensure_talk_room() {
  local uid="$1" password="$2" key="$3" name="$4" readonly="$5" token output
  token="$(talk_room_token "$uid" "$password" "$key")"
  if [ -z "$token" ]; then
    if ! output="$(occ talk:room:create "$name" --user "$uid" --owner "$uid" 2>&1)"; then
      echo "ERROR: could not create the Talk conversation ${name}:" >&2
      echo "${output}" >&2
      return 1
    fi
    # The command prints "Room token: <token>" and the success line after it. The CR strip is
    # the Windows guard, the same one app_password needs.
    token="$(printf '%s\n' "$output" | tr -d '\r' | sed -n 's/^Room token: //p' | head -n1)"
    if [ -z "$token" ]; then
      echo "ERROR: talk:room:create printed no token for ${name}:" >&2
      echo "${output}" >&2
      return 1
    fi
    echo "talk conversation ${name}: created (${token})"
  else
    echo "talk conversation ${name}: exists (${token})"
  fi
  # The write protection is established on every run instead of only at the create. It is the
  # object the negative case is measured on, so a conversation somebody switched back to
  # read-write would turn that test green for the wrong reason. `--readonly 0` says the same
  # thing about the writable one, and both directions are idempotent.
  if ! output="$(occ talk:room:update "$token" --readonly "$readonly" 2>&1)"; then
    echo "ERROR: could not set readonly=${readonly} on the conversation ${name}:" >&2
    echo "${output}" >&2
    return 1
  fi
  echo "talk conversation ${name}: readonly=${readonly}"
}

app_password() {
  local uid="$1" password="$2" raw token
  # The name option of user:auth-tokens:add exists from Nextcloud 33 on (default name
  # there: cli); 32 refuses the call with "option does not exist". Detection from the help
  # text instead of a version comparison, so on 33 to 35 the call stays exactly what it
  # was (token mcp-exapp) and 32 gets the same call without a name
  # (.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-01-bootstrap.txt).
  local token_name_args=()
  if occ user:auth-tokens:add --help 2>/dev/null | tr -d '\r' | grep -- '--name' >/dev/null; then
    token_name_args=(--name "$TOKEN_NAME")
  fi
  raw="$(occ_pw "$password" user:auth-tokens:add "$uid" \
    --password-from-env ${token_name_args[@]+"${token_name_args[@]}"})"
  # The command prints a label line and the token on the next line. The CR strip is the
  # Windows guard: Git Bash keeps the CR from the container output otherwise.
  token="$(printf '%s\n' "$raw" | tr -d '\r' | sed '/^[[:space:]]*$/d' | tail -n1 |
    sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  if [ -z "$token" ] || [ "${#token}" -lt 20 ]; then
    echo "ERROR: no app password could be parsed for ${uid}. Raw output:" >&2
    printf '%s\n' "$raw" >&2
    return 1
  fi
  printf '%s' "$token"
}

# Both secrets this script handles are bearer equivalent, so both are checked against the
# one shape `openssl rand -hex 32` produces. Anything else is a hand written value or the
# placeholder from .env.exapp.example, and that file is published in git: whoever reads it
# could impersonate every account of the instance with APP_SECRET, or attach a foreign FRP
# client to HaRP with HP_SHARED_KEY (CR-02). A weak value is refused, never adopted.
require_hex64() {
  local name="$1" value="$2" origin="$3"
  local re='^[0-9a-f]{64}$'
  if ! [[ "$value" =~ $re ]]; then
    echo "ERROR: ${name} in ${origin} is not 64 lower case hex characters." >&2
    echo "It looks like a placeholder or a hand written value, and both are secrets that" >&2
    echo "grant full access. Generate one: openssl rand -hex 32" >&2
    return 1
  fi
}

# json_info interpolates the port unquoted and the registry into a string of the
# registration payload, and all three source variables are overridable from the calling
# shell (IN-07). A forgotten export in that shell (the same error class WR-07 pinned
# COMPOSE_FILE against) produces at best invalid JSON, at worst a payload with extra
# fields that AppAPI adopts silently. APP_SECRET is covered by require_hex64 (CR-02);
# these two shapes are pinned here, immediately before any of them is used.
# Every check below is the ERE match of bash itself against the whole value, so ^ and $
# anchor at the edges of the string and an embedded LF or CR fails closed. grep would judge
# each line on its own and let a second line ride along into the payload.
require_port_number() {
  local name="$1" value="$2"
  local re='^[0-9]+$'
  if ! [[ "$value" =~ $re ]]; then
    echo "ERROR: ${name} is '${value}', not a plain port number." >&2
    echo "It is interpolated unquoted into the registration JSON (IN-07). Refusing." >&2
    return 1
  fi
}

require_registry_shape() {
  local value="$1"
  local re='^[0-9A-Za-z_.:-]+$'
  if ! [[ "$value" =~ $re ]]; then
    echo "ERROR: NC_EXAPP_REGISTRY is '${value}', which is not a host[:port] shape." >&2
    echo "It is interpolated into the registration JSON (IN-07). Refusing." >&2
    return 1
  fi
}

# The public address is the third value of that class (WR-03, same reason as IN-07): it is
# overridable from the calling shell and it lands as "value":"${PUBLIC_URL}" in the string
# of the json_info payload, unescaped. A value carrying a quotation mark produces invalid
# JSON at best and extra fields AppAPI adopts silently at worst, which is why it is pinned
# here rather than trusted because a default built it. The value is not echoed back: it can
# come from a staging environment file, and the name is what the caller has to fix.
# The check is the ERE match of bash itself against the whole value, so ^ and $ anchor at
# the edges of the string and a value with an embedded LF or CR fails closed instead of
# passing on its first line and smuggling the rest into the payload. grep is line based and
# its -z switch is GNU only, which let a two line address through on macOS (PR #26). The
# pattern sits in a variable because bash 3.2 and bash 5 both read an unquoted $re as a regex.
require_url_shape() {
  local name="$1" value="$2"
  local re='^https?://[A-Za-z0-9._:-]+(/[A-Za-z0-9._/-]*)?$'
  if ! [[ "$value" =~ $re ]]; then
    echo "ERROR: ${name} is not a plain http or https address." >&2
    echo "It is interpolated into the registration JSON (WR-03, IN-07). Refusing." >&2
    return 1
  fi
}

# The shared key is read back from the running HaRP container instead of being invented
# here. Both sides have to carry the same value, and a generated one would silently drift
# away from the container that was started before this script ran.
harp_shared_key() {
  local key
  key="$(docker inspect "${HARP_CONTAINER}" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null |
    tr -d '\r' | sed -n 's/^HP_SHARED_KEY=//p' | head -n1)"
  if [ -z "$key" ]; then
    echo "ERROR: container ${HARP_CONTAINER} is not running or carries no HP_SHARED_KEY." >&2
    echo "Start the topology first: $(compose_hint) up -d --wait" >&2
    return 1
  fi
  require_hex64 HP_SHARED_KEY "$key" "container ${HARP_CONTAINER}" || return 1
  printf '%s' "$key"
}

# The version is the single source of truth for the image tag, so it is read from the
# manifest instead of being repeated here.
app_version() {
  sed -n 's:.*<version>\(.*\)</version>.*:\1:p' appinfo/info.xml | head -n1 | tr -d '\r'
}

# Fixed across runs: a new secret on every registration locks out a container or a
# development process that still holds the old one (research pitfall 11). Pinning an
# existing value is exactly why it has to be validated first: a bad one would be held on
# to across every further run, and .env.exapp.example ships a placeholder that the obvious
# `cp .env.exapp.example .env.exapp` would turn into the real registration secret (CR-02).
app_secret() {
  local existing=""
  if [ -f "${ENV_FILE}" ]; then
    existing="$(sed -n 's/^APP_SECRET=//p' "${ENV_FILE}" | head -n1 | tr -d '\r')"
  fi
  if [ -n "$existing" ]; then
    require_hex64 APP_SECRET "$existing" "${ENV_FILE}" || return 1
    printf '%s' "$existing"
    return 0
  fi
  openssl rand -hex 32
}

ensure_daemon_harp() {
  local output
  if occ app_api:daemon:list 2>/dev/null | grep "${DAEMON_NAME}" >/dev/null; then
    echo "daemon ${DAEMON_NAME}: exists"
    return 0
  fi
  # nextcloud_url is passed explicitly: without it AppAPI replaces https by http, and the
  # deploy daemon has to reach Nextcloud through the same reverse proxy that serves
  # /exapps/, otherwise the heartbeat fails (research pitfall 7). On the staging topology
  # that URL is the public https one; compose.staging.yml gives the reverse proxy the
  # public host name as a network alias, so the call stays inside the compose network and
  # still lands on the certificate that name belongs to.
  #
  # HP_SHARED_KEY is bearer equivalent (CR-02, WR-11), so it travels through stdin like
  # every other secret of this script (WR-06) and never through the argv of the docker
  # client on the host. The remaining argv inside the container is the same residual risk
  # WR-06 already documents and accepts for the json-info payload.
  if ! output="$(printf '%s' "${HP_SHARED_KEY}" | occ_stdin \
    'KEY="$(cat)"; exec php occ app_api:daemon:register "$@" --harp_shared_key "$KEY"' \
    "${DAEMON_NAME}" "Harp Proxy (Docker)" docker-install http \
    "appapi-harp:8780" "${NC_DAEMON_URL}" \
    --net "${NETWORK_NAME}" --harp \
    --harp_frp_address "appapi-harp:8782" \
    --set-default 2>&1)"; then
    echo "ERROR: could not register the deploy daemon ${DAEMON_NAME}:" >&2
    echo "${output}" >&2
    return 1
  fi
  echo "daemon ${DAEMON_NAME}: registered"
}

ensure_image() {
  local ref="${REGISTRY}/${IMAGE_NAME}:${APP_VERSION}" output
  if ! output="$(docker buildx build --platform linux/amd64 --load -t "${ref}" . 2>&1)"; then
    echo "ERROR: could not build ${ref}:" >&2
    echo "${output}" >&2
    return 1
  fi
  if ! output="$(docker push "${ref}" 2>&1)"; then
    echo "ERROR: could not push ${ref} into the local registry:" >&2
    echo "${output}" >&2
    echo "Is the registry service up? $(compose_hint) ps registry" >&2
    return 1
  fi
  IMAGE_DIGEST="$(docker inspect --format '{{index .RepoDigests 0}}' "${ref}" 2>/dev/null |
    tr -d '\r' | cut -d@ -f2)"
  if [ -z "${IMAGE_DIGEST}" ]; then
    echo "ERROR: the push of ${ref} left no digest behind, so nothing can be verified." >&2
    return 1
  fi
  echo "image ${ref}: built and pushed (${IMAGE_DIGEST})"
}

# The loopback registry has neither authentication nor TLS, so every local process, down to
# a package postinstall script, may `docker push` over this tag. The deploy daemon pulls by
# tag, and what it pulls is started with APP_SECRET in its environment (WR-09). A tag is a
# name, a digest is the content: this compares what the registry serves now against what we
# pushed, immediately before the registration that triggers the pull.
verify_image_digest() {
  local ref="${REGISTRY}/${IMAGE_NAME}:${APP_VERSION}" remote
  remote="$(docker buildx imagetools inspect "${ref}" --format '{{.Manifest.Digest}}' 2>/dev/null |
    tr -d '\r' | tr -d '[:space:]')"
  if [ -z "$remote" ]; then
    echo "ERROR: could not read the digest of ${ref} from the registry." >&2
    return 1
  fi
  if [ "$remote" != "${IMAGE_DIGEST}" ]; then
    echo "ERROR: ${ref} in the registry is not the image this run built." >&2
    echo "  pushed:  ${IMAGE_DIGEST}" >&2
    echo "  serving: ${remote}" >&2
    echo "Someone else pushed over this tag. Refusing to register it (WR-09)." >&2
    return 1
  fi
  echo "image digest ${remote}: unchanged since the push"
}

# The registration overrides exactly three fields of the manifest: registry, image and
# image tag. appinfo/info.xml keeps pointing at ghcr.io because that is the store state
# (D-25 publishes nothing before phase 5), while the local test needs an image that
# actually exists, and that one lives in the loopback registry.
#
# The four backslashes in each well-known route are two levels of escaping: the unquoted
# heredoc consumes one pair, and JSON needs the remaining one so the route regex reaches
# AppAPI as ^/\.well-known/... with an escaped dot. Two backslashes here produce the
# invalid JSON escape \. and AppAPI answers "Invalid app info provided in JSON format".
# Every pattern ends with $, and every route is access level 0 (PUBLIC): HaRP matches with
# re.match, the 401 of the OAuth discovery flow has to come from the ExApp itself, and the
# browser onboarding of plan 03-04 is used by a person who is not necessarily signed in to
# Nextcloud yet. The four routes of the authorization server (plan 03-05) are public for
# their own reasons: /authorize is a browser route and HaRP knows no sign in redirect, and
# /token, /register and /revoke carry their own controls and no user session at all. The
# connections page of plan 04-03 is the thirteenth and is public for the reason its own
# manifest comment gives: the identity check happens in the app
# (appinfo/info.xml carries the full reasoning, plans 03-01, 03-04, 03-05 and 04-03).
#
# headers_to_exclude mirrors appinfo/info.xml: the proxy strips the headers it sets itself,
# so a client cannot send a second AUTHORIZATION-APP-API next to the real one (WR-01).
#
# Daemon and port are parameters, so the development loop builds its payload the same way
# instead of rewriting this one with sed.
# The one deploy option this topology sets, and it is not cosmetic: the authorization
# server calls itself by NC_MCP_PUBLIC_URL, so without it every discovery document, every
# issuer and every resource_metadata pointer names the documented default
# http://127.0.0.1:8765 and no client can complete a connection (measured in plan 03-08).
#
# It travels in the payload and not as `--env`, because the two registration paths of
# AppAPI are not equivalent: the info.xml path normalises
# external-app/environment-variables into the map the deploy daemon reads and lets `--env`
# override a declared variable, while the json-info path hands the decoded object through
# untouched (ExAppService::getAppInfo, verified in the running AppAPI 34.0.0). So the
# already normalised shape is what a json-info registration has to carry, and `--env`
# alone is accepted and silently dropped. appinfo/info.xml declares the same six
# variables for the installation that registers from the manifest.
EXCLUDED_HEADERS='["AUTHORIZATION-APP-API","EX-APP-ID","EX-APP-VERSION","AA-VERSION","X-ORIGIN-IP"]'
json_info() {
  local daemon="$1" port="$2"
  cat <<JSON
{"external-app":{"environment-variables":{"NC_MCP_PUBLIC_URL":{"name":"NC_MCP_PUBLIC_URL","value":"${PUBLIC_URL}"}}},"id":"${APP_ID}","name":"${APP_NAME}","daemon_config_name":"${daemon}","version":"${APP_VERSION}","secret":"${APP_SECRET}","port":${port},"docker-install":{"registry":"${REGISTRY}","image":"${IMAGE_NAME}","image-tag":"${APP_VERSION}"},"routes":[{"url":"^/mcp/?$","verb":"GET,POST,DELETE","access_level":0,"headers_to_exclude":${EXCLUDED_HEADERS}},{"url":"^/\\\\.well-known/oauth-protected-resource/mcp$","verb":"GET","access_level":0,"headers_to_exclude":${EXCLUDED_HEADERS}},{"url":"^/\\\\.well-known/openid-configuration$","verb":"GET","access_level":0,"headers_to_exclude":${EXCLUDED_HEADERS}},{"url":"^/\\\\.well-known/oauth-authorization-server$","verb":"GET","access_level":0,"headers_to_exclude":${EXCLUDED_HEADERS}},{"url":"^/connect/wait/?$","verb":"GET","access_level":0,"headers_to_exclude":${EXCLUDED_HEADERS}},{"url":"^/connect/?$","verb":"GET,POST","access_level":0,"headers_to_exclude":${EXCLUDED_HEADERS}},{"url":"^/authorize/?$","verb":"GET,POST","access_level":0,"headers_to_exclude":${EXCLUDED_HEADERS}},{"url":"^/authorize/consent/?$","verb":"GET","access_level":0,"headers_to_exclude":${EXCLUDED_HEADERS}},{"url":"^/authorize/decide/?$","verb":"POST","access_level":0,"headers_to_exclude":${EXCLUDED_HEADERS}},{"url":"^/token/?$","verb":"POST","access_level":0,"headers_to_exclude":${EXCLUDED_HEADERS}},{"url":"^/register/?$","verb":"POST","access_level":0,"headers_to_exclude":${EXCLUDED_HEADERS}},{"url":"^/revoke/?$","verb":"POST","access_level":0,"headers_to_exclude":${EXCLUDED_HEADERS}},{"url":"^/connections/?$","verb":"GET,POST","access_level":0,"headers_to_exclude":${EXCLUDED_HEADERS}}]}
JSON
}

# The payload carries "secret":"<APP_SECRET>", which is bearer equivalent, so it goes in
# through stdin and never as an argument of the docker client (WR-06).
register_exapp() {
  local daemon="$1" port="$2"
  local snippet
  snippet='JSON="$(cat)"; exec php occ app_api:app:register "$1" "$2"'
  snippet="${snippet} "'--json-info "$JSON" --force-scopes --wait-finish'
  json_info "$daemon" "$port" | occ_stdin "${snippet}" "${APP_ID}" "$daemon"
}

# access_level travels as a number on purpose. AppAPI maps the names PUBLIC, USER and
# ADMIN to 0, 1 and 2 only on the info.xml path (ExAppService::getAppInfo); a json-info
# registration writes the value straight into the integer column of ex_apps_routes, and a
# route whose access level reads "USER" is a route HaRP cannot evaluate. All thirteen routes
# carry 0 (PUBLIC), the connections page of plan 04-03 included: HaRP resolves the signed in
# account on a PUBLIC route as well and the app compares it itself, while a USER declaration
# would feed the HaRP blacklist with the refusals those pages produce as normal traffic and
# answer the whole ExApp with 502 (CR-01, appinfo/info.xml carries the full reasoning).
ensure_exapp() {
  local output
  if occ app_api:app:list 2>/dev/null | grep "${APP_ID}" >/dev/null; then
    echo "exapp ${APP_ID}: registered"
    return 0
  fi
  verify_image_digest || return 1
  if ! output="$(register_exapp "${DAEMON_NAME}" "${APP_PORT}" 2>&1)"; then
    echo "ERROR: could not register the ExApp ${APP_ID}:" >&2
    echo "${output}" >&2
    echo "Logs: $(compose_hint) logs --tail=100 appapi-harp" >&2
    echo "See the FALLBACK block at the end of this script." >&2
    return 1
  fi
  echo "exapp ${APP_ID}: registered and deployed"
}

# `occ app_api:app:list` prints one line per app: "<id> (<name>): <version> [enabled]".
# Enabling is not cosmetic: AppAPI sends PUT /enabled?enabled=1 to the container and only
# writes the flag when the app answers 200 with an empty error field.
ensure_exapp_enabled() {
  local output
  if occ app_api:app:list 2>/dev/null | tr -d '\r' | grep "^${APP_ID} .*\[enabled\]" >/dev/null; then
    echo "exapp ${APP_ID}: enabled"
    return 0
  fi
  if ! output="$(occ app_api:app:enable "${APP_ID}" 2>&1)"; then
    echo "ERROR: could not enable the ExApp ${APP_ID}:" >&2
    echo "${output}" >&2
    return 1
  fi
  echo "exapp ${APP_ID}: enabled"
}

# The development loop: no image, no container, a locally started process instead. Only
# reached with --manual, because it registers a second daemon and a second app entry.
register_manual_install() {
  local output
  # The daemon host carries no port: AppAPI up to stable32 appends the port of the ExApp
  # to the host (host.docker.internal:23001:23001, "Invalid host"), from stable33 on it
  # cuts a port off. Without a port 32, 34 and 35 build the same heartbeat URL
  # http://host.docker.internal:23001 (measured, raw/32-01-bootstrap.txt of phase 32).
  if ! occ app_api:daemon:list 2>/dev/null | grep "${MANUAL_DAEMON_NAME}" >/dev/null; then
    if ! output="$(occ app_api:daemon:register \
      "${MANUAL_DAEMON_NAME}" "Manual Install" manual-install http \
      "host.docker.internal" "${NC_DAEMON_URL}" 2>&1)"; then
      echo "ERROR: could not register the manual-install daemon:" >&2
      echo "${output}" >&2
      return 1
    fi
    echo "daemon ${MANUAL_DAEMON_NAME}: registered"
  fi
  if occ app_api:app:list 2>/dev/null | grep "${APP_ID}" >/dev/null; then
    echo "exapp ${APP_ID}: already registered, unregister it first to switch the daemon"
    return 0
  fi
  if ! output="$(register_exapp "${MANUAL_DAEMON_NAME}" "${MANUAL_APP_PORT}" 2>&1)"; then
    echo "ERROR: could not register the ExApp in manual-install mode:" >&2
    echo "${output}" >&2
    return 1
  fi
  echo "exapp ${APP_ID}: registered against the local process on port ${MANUAL_APP_PORT}"
}

echo "== ExApp topology bootstrap =="
if [ "${STAGING_MODE}" -eq 1 ]; then
  echo "mode: staging, public base ${BASE_URL}"
fi
ensure_own_topology
require_port_number NC_EXAPP_APP_PORT "${APP_PORT}"
require_port_number NC_EXAPP_MANUAL_PORT "${MANUAL_APP_PORT}"
require_registry_shape "${REGISTRY}"
require_url_shape NC_EXAPP_PUBLIC_URL "${PUBLIC_URL}"
if [ "${STAGING_MODE}" -eq 1 ]; then
  require_host_name "${STAGING_DOMAIN}"
  require_generated_password NC_EXAPP_ALICE_PASSWORD "${ALICE_PASSWORD}"
  require_generated_password NC_EXAPP_BOB_PASSWORD "${BOB_PASSWORD}"
fi
wait_for_install

# Notes and Deck are optional apps; the tool plans of the later phases need both.
ensure_app notes
ensure_app deck
# Tables is the tool family of this phase, Mail is the family the reachability spike of
# MAIL-04 measures. Both are optional store apps, so both go through the same idempotent
# install-or-enable step as the two above.
ensure_app tables
ensure_app mail
# Talk is the tool family of phase 9. Chat needs no signaling backend at all: the two routes
# this connector builds are plain OCS calls against the database, and the internal signaling
# server covers the rest, so this install step is as cheap as the two above. The app id is
# `spreed`, not `talk`.
ensure_app spreed

# alice is the full test user, bob is the restricted one for the permission tests.
ensure_user alice "${ALICE_PASSWORD}"
ensure_user bob "${BOB_PASSWORD}"

# The spike account of MAIL-04, since plan 10-01 pointed at the GreenMail service of this
# topology. It has to come after ensure_user and not next to the ensure_app lines above: on a
# fresh topology alice does not exist yet at that point, and `mail:account:create-imap` for an
# unknown user is an error, not a no-op. alice is the account the connection file publishes as
# NC_MCP_TEST_USER.
ensure_mail_account alice "Alice Spike" alice@example.test "${ALICE_IMAP_PASSWORD}" \
  "${MAIL_HOST}" "${MAIL_IMAP_PORT}"
deliver_test_mail alice alice@example.test "${ALICE_IMAP_PASSWORD}"
sync_mail_account alice

ensure_calendar alice personal
ensure_addressbook alice contacts
ensure_calendar bob personal

# Initialise both file homes so a WebDAV SEARCH answers an empty result, not a 500 (see
# ensure_files_home). bob is the one the leak tests search before he owns anything.
ensure_files_home alice
ensure_files_home bob

# The third data layer of success criterion 3 (see the block above ensure_readonly_share).
# All names carry the same pinned suffix, so a second run works on the same objects.
SHARE_SUFFIX="$(share_suffix)"
SHARED_DIR="/mcp-share-${SHARE_SUFFIX}"
SHARED_MARKER="mcp-shared-file-${SHARE_SUFFIX}"
SHARED_FILE="${SHARED_DIR}/${SHARED_MARKER}.md"
PRIVATE_MARKER="mcp-private-${SHARE_SUFFIX}"
PRIVATE_FILE="/${PRIVATE_MARKER}.md"
ensure_readonly_share alice "${ALICE_PASSWORD}" bob "${BOB_PASSWORD}"

# The two Talk test conversations (see the block above talk_room_token). They stand here and
# not next to the `ensure_app` lines above for the same reason ensure_mail_account does: on a
# fresh topology alice does not exist at that point, and `talk:room:create --user alice` for an
# unknown user is an error and not a no-op. The names live in these four lines only and reach
# tests/integration/test_talk_roundtrip.py through the connection file at the end of this
# script, so a rename is one edit. The ASCII prefix is what the lookup matches on; the umlauts
# behind it are there so a broken encoding shows up in the first run instead of never.
#
# No spaces in either name, and that is not cosmetic: the connection file below is read with
# `set -a && . ./.env.exapp`, and an unquoted value with a space in it makes the shell run its
# second word as a command. Hyphens carry the same reading and survive every consumer of that
# file, quoting rules included.
TALK_ROOM_OPEN_KEY="MCP-Talk-offen"
TALK_ROOM_LOCKED_KEY="MCP-Talk-nurlesen"
TALK_ROOM_OPEN="${TALK_ROOM_OPEN_KEY}-Grüße-aus-Hamburg"
TALK_ROOM_LOCKED="${TALK_ROOM_LOCKED_KEY}-Straße-ohne-Ausgang"
ensure_talk_room alice "${ALICE_PASSWORD}" "${TALK_ROOM_OPEN_KEY}" "${TALK_ROOM_OPEN}" 0
ensure_talk_room alice "${ALICE_PASSWORD}" "${TALK_ROOM_LOCKED_KEY}" "${TALK_ROOM_LOCKED}" 1

# Nextcloud counts failed logins per source IP, and a remote MCP server is one IP for many
# users. The negative tests produce 401s on purpose, so the guard would throttle the whole
# run and hand us random 429s (research pitfall 8). Test instance only, never a
# recommendation for a real server, and never on the staging instance: that one is on the
# public internet, nothing automated hammers it, and a public Nextcloud with the guard
# switched off is an invitation to guess the two accounts it carries.
if [ "${DISABLE_BRUTEFORCE}" -eq 1 ]; then
  occ config:system:set auth.bruteforce.protection.enabled --value=false --type=boolean >/dev/null
  echo "bruteforce protection: disabled (test instance)"
  # The per-user rate limits of the OCS routes are a second, separate guard. The canary
  # world creates and removes shares in four modes within a minute, and on the first CI
  # run on 35.0.1 (run 36810316714) the share creation answered 429 after the second
  # mode. Same reasoning, same scope: test instance only.
  occ config:system:set ratelimit.protection.enabled --value=false --type=boolean >/dev/null
  echo "rate limit protection: disabled (test instance)"
else
  echo "bruteforce protection: left enabled (public instance)"
fi

# AppAPI is an app store app, not part of the server tarball (research pitfall 9). Recent
# server images ship it, in which case app:install reports it as already installed.
ensure_app app_api

HP_SHARED_KEY="$(harp_shared_key)"
APP_VERSION="$(app_version)"
APP_SECRET="$(app_secret)"

ensure_daemon_harp

if [ "${MANUAL_MODE}" -eq 1 ]; then
  register_manual_install
else
  ensure_image
  ensure_exapp
  ensure_exapp_enabled
fi

ALICE_APP_PASSWORD="$(app_password alice "${ALICE_PASSWORD}")"
BOB_APP_PASSWORD="$(app_password bob "${BOB_PASSWORD}")"
echo "app passwords: created for alice and bob"

umask 077
cat >"${ENV_FILE}" <<EOF
# Written by scripts/bootstrap_exapp.sh. Never commit this file.
NC_MCP_URL=${BASE_URL}
NC_MCP_EXAPP_BASE=${PUBLIC_URL}
NC_MCP_PUBLIC_URL=${PUBLIC_URL}
NC_MCP_TEST_USER=alice
NC_MCP_TEST_APP_PASSWORD=${ALICE_APP_PASSWORD}
NC_MCP_TEST_USER2=bob
NC_MCP_TEST_APP_PASSWORD2=${BOB_APP_PASSWORD}
# The read-only share of plan 05-03, as paths relative to the root of each user: alice owns
# both, bob sees the folder and the file in it and never the private one. The marker is in
# the name and in the content of the shared file, so a search hit and a read can be asserted
# on the same string. tests/integration/test_permission_parity_share.py skips without them.
#
# Without the leading slash, and that is not cosmetic: Git Bash rewrites an environment value
# that looks like an absolute POSIX path when it starts a native process, so an exported
# /mcp-share-x/f.md reaches pytest as C:/Program Files/Git/mcp-share-x/f.md and every path
# assertion measures the MSYS installation directory (measured on this host, 19.08.2026). A
# value relative to the user's root is the same string on every platform, and the test puts
# the slash back where the tools want it.
NC_MCP_TEST_SHARED_DIR=${SHARED_DIR#/}
NC_MCP_TEST_SHARED_FILE=${SHARED_FILE#/}
NC_MCP_TEST_PRIVATE_FILE=${PRIVATE_FILE#/}
NC_MCP_TEST_SHARED_MARKER=${SHARED_MARKER}
# The two Talk test conversations of plan 09-05, both owned by NC_MCP_TEST_USER: one writable
# and one write protected, and the write protected one carries the negative case of TALK-03.
# The names are defined once in this script and travel through this file, so
# tests/integration/test_talk_roundtrip.py never spells them a second time; without them it
# skips instead of failing.
NC_MCP_TEST_TALK_ROOM=${TALK_ROOM_OPEN}
NC_MCP_TEST_TALK_READONLY_ROOM=${TALK_ROOM_LOCKED}
# The account passwords of the two throwaway users. The OAuth flow check of plan 03-08
# needs them because it walks the Nextcloud sign in of the Login Flow v2 without a
# browser; nothing in src/ ever reads a user password, and this file is git-ignored.
NC_MCP_TEST_PASSWORD=${ALICE_PASSWORD}
NC_MCP_TEST_PASSWORD2=${BOB_PASSWORD}
APP_ID=${APP_ID}
APP_SECRET=${APP_SECRET}
APP_VERSION=${APP_VERSION}
HP_SHARED_KEY=${HP_SHARED_KEY}
EOF
echo "wrote ${ENV_FILE}"

echo
echo "== verification =="
occ app_api:daemon:list
occ app_api:app:list
if ! occ app_api:app:list | grep "${APP_ID}" >/dev/null; then
  echo "ERROR: ${APP_ID} is not in the ExApp list." >&2
  exit 1
fi
if ! occ app_api:app:list | tr -d '\r' | grep "^${APP_ID} .*\[enabled\]" >/dev/null; then
  echo "ERROR: ${APP_ID} is registered but not enabled." >&2
  exit 1
fi

echo
echo "Ready. The app answers under:"
echo "  ${PUBLIC_URL}/mcp"

# ---------------------------------------------------------------------------
# FALLBACK 1: no app store access for app_api (research pitfall 9)
#
# `occ app:install app_api` downloads from apps.nextcloud.com. In an offline runner or
# behind a proxy that blocks it, the command fails, `app:enable` fails as well, and this
# script stops at ensure_app. Recent nextcloud images ship app_api, so the step then only
# prints "already installed".
#
# Then install it by hand once and let the script enable it:
#
#   1. Download the release archive on a machine that has access:
#      https://github.com/nextcloud/app_api/releases (pick the tag that matches the
#      server version of the running image: 34.x for the default of compose.exapp.yml,
#      35.x when NC_EXAPP_NEXTCLOUD_IMAGE points at a 35 image).
#   2. Unpack it into the container so the app directory keeps its plain name:
#        docker compose -f compose.exapp.yml cp app_api nextcloud:/var/www/html/custom_apps/app_api
#        docker compose -f compose.exapp.yml exec -T --user root nextcloud \
#          chown -R www-data:www-data /var/www/html/custom_apps/app_api
#   3. Re-run this script: `occ app:install` still fails, `occ app:enable` now succeeds.
#
# FALLBACK 2: the app answers 401 after a re-registration (research pitfall 11)
#
# APP_SECRET is generated fresh on every registration unless the registration carries one.
# This script pins it: the value from .env.exapp is passed in the json-info payload, so a
# re-registration keeps the secret stable. If .env.exapp was deleted, a new secret is
# generated, and then everything that still holds the old one has to be restarted:
#
#   docker compose -f compose.exapp.yml exec -T --user www-data nextcloud \
#     php occ app_api:app:unregister mcp_connector
#   rm -f .env.exapp        # only if you want a new secret on purpose
#   bash scripts/bootstrap_exapp.sh
#
# In the --manual development loop the local process is the one that holds the old secret:
# restart `nc-mcp-exapp` after every registration, otherwise every incoming request is
# answered with 401 and every outgoing one is rejected by Nextcloud.
# ---------------------------------------------------------------------------
