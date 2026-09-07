#!/usr/bin/env bash
# Install Findling (PHP half and ExApp backend) on the test topology, for BL-02.
#
# tests/integration/test_content_hit_fidelity.py measures the content-hit permission
# fidelity of the Findling synergy and skips when the findling provider is missing.
# This script builds the state the test needs, from the real store artifacts: the PHP
# half from the GitHub release of the tag (the same archive the store serves), the
# backend over the AppAPI daemon with the info.xml of that release, which points at
# the public ghcr image. Nothing here is a mock; the chain the test measures is the
# chain a selfhoster gets.
#
# Environment, all optional:
#   FINDLING_VERSION   release tag without the v, default 1.0.1
#   NC_CONTAINER       the Nextcloud container, default nc-mcp-exapp-nc
#   DAEMON_NAME        the AppAPI deploy daemon, default harp_proxy_docker
set -euo pipefail

FINDLING_VERSION="${FINDLING_VERSION:-1.0.1}"
NC_CONTAINER="${NC_CONTAINER:-nc-mcp-exapp-nc}"
DAEMON_NAME="${DAEMON_NAME:-harp_proxy_docker}"
BASE="https://github.com/street1983nk/nextcloud-search/releases/download/v${FINDLING_VERSION}"

# docker exec arguments like /var/www/html run with MSYS path conversion off, so a Git
# Bash on Windows does not rewrite them; docker cp keeps the conversion, because its host
# half is a real host path and its container half carries a colon, which MSYS leaves
# alone. On Linux the variable is inert either way.
dockerx() {
  MSYS_NO_PATHCONV=1 docker "$@"
}

occ() {
  dockerx exec --user www-data "${NC_CONTAINER}" php occ "$@"
}

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT

echo "fetching the two release archives of v${FINDLING_VERSION}"
curl -sfL "${BASE}/findling.tar.gz" -o "${workdir}/findling.tar.gz"
curl -sfL "${BASE}/findling_backend.tar.gz" -o "${workdir}/findling_backend.tar.gz"
tar -xzf "${workdir}/findling.tar.gz" -C "${workdir}"
tar -xzf "${workdir}/findling_backend.tar.gz" -C "${workdir}"

echo "installing the PHP half into custom_apps"
docker cp "${workdir}/findling" "${NC_CONTAINER}:/var/www/html/custom_apps/findling"
dockerx exec --user root "${NC_CONTAINER}" chown -R www-data:www-data \
  /var/www/html/custom_apps/findling
occ app:enable findling

echo "registering the backend over the ${DAEMON_NAME} daemon"
docker cp "${workdir}/findling_backend/appinfo/info.xml" "${NC_CONTAINER}:/tmp/findling-backend-info.xml"
# Idempotent on purpose: a rerun after a broken registration must not die on the
# leftover half. unregister answers non zero when nothing is registered, which is fine.
occ app_api:app:unregister findling_backend --silent --force >/dev/null 2>&1 || true
occ app_api:app:register findling_backend "${DAEMON_NAME}" \
  --info-xml /tmp/findling-backend-info.xml --wait-finish
occ app_api:app:enable findling_backend

echo "findling ${FINDLING_VERSION} is installed; the first index starts with the next cron rounds"
