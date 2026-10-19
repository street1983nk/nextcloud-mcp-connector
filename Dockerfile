# syntax=docker/dockerfile:1
#
# ExApp container image for the AppAPI deploy daemon (EXAPP-01, D-25).
#
# Two stages, because uv and the build tool chain have no business in a published image:
# the build stage resolves the locked environment, the runtime stage carries that
# environment plus curl and frpc, and nothing else.
#
# There is no EXPOSE. AppAPI passes APP_PORT to the container at start time, and behind
# HaRP there is no TCP port at all (unix socket plus frpc tunnel), so an EXPOSE would only
# document a number this image cannot know.

# --------------------------------------------------------------------------------------
# Build stage: resolve the locked dependency set
# --------------------------------------------------------------------------------------
# Pinned by digest for the same reason the uv line below pins a release: the tag
# 3.13-slim moves, the digest does not, and dependabot's docker pass moves the digest
# deliberately instead of a rebuild moving it silently. The digest is the multi-arch
# index, so amd64 and arm64 both resolve under it.
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS build

# A pinned uv release from the official image instead of a curl-pipe-shell installer: the
# image tag is what resolves the dependency set, and a moving "latest" would make the
# build irreproducible (T-02-24).
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src

# --frozen: uv.lock is the truth. A pyproject.toml that drifted away from it fails the
# build here instead of quietly resolving something else into the image (T-02-24).
# --no-dev leaves pytest, ruff, pyright and vulture out.
# --no-editable installs the package itself into the environment, so the runtime stage
# needs the virtual environment alone and never a copy of src.
RUN uv sync --frozen --no-dev --no-editable --extra documents

# --------------------------------------------------------------------------------------
# Runtime stage
# --------------------------------------------------------------------------------------
# Same digest as the build stage, and it has to stay the same value: two stages on two
# different base snapshots would ship a runtime libc the build never saw.
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS runtime

# Provenance in the image itself, so a later security response does not have to guess
# where this thing came from (T-02-26). A cosign signature belongs to the store
# submission in phase 5.
LABEL org.opencontainers.image.source="https://github.com/street1983nk/nextcloud-mcp-connector" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.title="MCP Connector"

# curl is not a convenience: the HaRP integration requires it in the image, and the
# healthcheck below is built on it. ca-certificates keeps outgoing HTTPS to Nextcloud
# working when the deploy daemon does not inject its own certificates.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# frpc, the tunnel client HaRP expects beside the application (start.sh launches it).
# Version and both checksums are copied verbatim from the HaRP README, section "Adapting
# ExApps to use HaRP" (github.com/nextcloud/HaRP, branch main, retrieved 2026-08-15), the
# same section that publishes start.sh. sha256sum -c turns a tampered or replaced release
# asset into a failed build instead of a running foreign binary (T-02-SC).
#
# Version and checksums are constants of this RUN, not ARGs (IN-03). As build arguments
# they could be replaced from the command line with --build-arg, so the pinning statement
# only held for a build nobody tampered with, which is not what a pin is for.
ARG TARGETARCH
RUN set -eux; \
    FRP_VERSION=0.61.1; \
    FRP_AMD64_SHA256=bff260b68ca7b1461182a46c4f34e9709ba32764eed30a15dd94ac97f50a2c40; \
    FRP_ARM64_SHA256=af6366f2b43920ebfe6235dba6060770399ed1fb18601e5818552bd46a7621f8; \
    case "${TARGETARCH:-amd64}" in \
        arm64) FRP_ARCH=arm64; FRP_SHA256="${FRP_ARM64_SHA256}" ;; \
        amd64) FRP_ARCH=amd64; FRP_SHA256="${FRP_AMD64_SHA256}" ;; \
        *) echo "unsupported target architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/frp.tar.gz \
        "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_${FRP_ARCH}.tar.gz"; \
    echo "${FRP_SHA256}  /tmp/frp.tar.gz" | sha256sum -c -; \
    tar -C /tmp -xzf /tmp/frp.tar.gz; \
    install -m 0755 "/tmp/frp_${FRP_VERSION}_linux_${FRP_ARCH}/frpc" /usr/local/bin/frpc; \
    rm -rf "/tmp/frp_${FRP_VERSION}_linux_${FRP_ARCH}" /tmp/frp.tar.gz

# One fixed unprivileged uid, created before anything is chowned to it (T-02-22). A root
# container would hold a docker managed volume and a shared secret with far more authority
# than an MCP responder needs.
RUN groupadd --gid 10001 exapp \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin exapp

COPY entrypoint.sh start.sh healthcheck.sh /
RUN chmod 0755 /entrypoint.sh /start.sh /healthcheck.sh \
    # start.sh writes /frpc.toml, and an unprivileged process cannot create a file in /.
    # It can truncate one it owns, which is exactly what the redirect in start.sh does,
    # so the file is pre-created here instead of loosening the permissions of /.
    && install -o 10001 -g 10001 -m 0600 /dev/null /frpc.toml \
    # AppAPI mounts the volume nc_app_<appid>_data at /nc_app_<appid>_data and passes that
    # path as APP_PERSISTENT_STORAGE (DockerActions::buildDefaultExAppVolume). A fresh
    # named volume inherits owner and mode of the directory it covers, so creating it here
    # is what makes the storage writable for the unprivileged process.
    && install -d -o 10001 -g 10001 -m 0700 /nc_app_mcp_connector_data \
    # HaRP installs the FRP client certificate into the running container and does it with
    # the identity of the container, so it runs `mkdir -p /certs/frp` as uid 10001. Without
    # this directory that command fails with "Permission denied", the certificate
    # installation answers 500, frpc falls back to a plaintext handshake, the FRP server
    # closes the connection, and every heartbeat is answered with 503 by HAProxy. Measured
    # in plan 02-04 against the real deploy daemon; start.sh reads the same path.
    && install -d -o 10001 -g 10001 -m 0700 /certs

# No --chown: the runtime user reads its own code, it never writes it (WR-13). With the
# environment owned by uid 10001, any bug that yields a single file write turns into
# persistence, because AppAPI restarts this container instead of recreating it, and the
# next start would run the replaced module with APP_SECRET in its environment. The three
# paths that do have to be writable are /nc_app_mcp_connector_data, /certs and /frpc.toml,
# and they are prepared above with 0700 and 0600.
COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

# The image sets no configuration at all, and no secret either (T-02-23). The DNS
# rebinding switch used to live here, unconditionally, which disarmed the Host and Origin
# check for every deployment mode and not only for the HaRP path it was meant for (WR-02).
# entrypoint.sh exports it when HP_SHARED_KEY says that HaRP is in front of us, and leaves
# it alone otherwise, where the check is the defence that belongs there.

WORKDIR /app
USER 10001:10001

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=6 CMD ["/healthcheck.sh"]

# entrypoint.sh, not start.sh: two guards run first, then the verbatim upstream script is
# exec'd with the same argument it always got (WR-02, WR-04).
ENTRYPOINT ["/entrypoint.sh", "nc-mcp-exapp"]
