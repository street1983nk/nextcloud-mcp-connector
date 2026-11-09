#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 street1983nk
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Build and sign the App Store release archive for this ExApp.
#
# The App Store artifact is NOT the Docker image. It is a tar.gz with a single
# top level folder "mcp_connector/" that contains at least appinfo/info.xml. The
# Docker image is only referenced from info.xml (docker-install) and is pulled by
# AppAPI at install time from ghcr.io. See docs/store-submission.md.
#
# Usage:
#   scripts/build_store_release.sh [VERSION]
#
# VERSION defaults to the <version> in appinfo/info.xml. The signing key is read
# from NC_SIGN_KEY (default ~/.nextcloud/certificates/mcp_connector.key).
#
# The signature printed at the end is over the LOCALLY built archive and exists
# only for the local store pipeline diagnosis (structure and signing sanity).
# It is NOT the signature the store accepts: tar.gz is not byte reproducible,
# so the store submission signature must be computed over the asset DOWNLOADED
# from the GitHub release (runbook step 6 in docs/store-submission.md). The
# 0.1.8 release measured the difference: 45710 bytes local vs 45546 published.
set -euo pipefail

APP_ID="mcp_connector"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY="${NC_SIGN_KEY:-$HOME/.nextcloud/certificates/${APP_ID}.key}"

VERSION="${1:-$(grep -oP '(?<=<version>)[^<]+' "$ROOT/appinfo/info.xml")}"
if [[ -z "$VERSION" ]]; then
  echo "error: could not determine version, pass it as the first argument" >&2
  exit 1
fi

OUT_DIR="$ROOT/dist"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# Assemble the top level folder the store expects. Keep it lean: the metadata the
# store reads, plus the changelog and license it lists. The store reads
# CHANGELOG.<code>.md per language, and the app management in Nextcloud shows
# the entry in the language of the signed-in user, so the German and French
# changelog travel next to the English one.
mkdir -p "$STAGE/$APP_ID/appinfo"
cp "$ROOT/appinfo/info.xml" "$STAGE/$APP_ID/appinfo/info.xml"
[[ -f "$ROOT/CHANGELOG.md" ]] && cp "$ROOT/CHANGELOG.md" "$STAGE/$APP_ID/CHANGELOG.md"
[[ -f "$ROOT/CHANGELOG.de.md" ]] && cp "$ROOT/CHANGELOG.de.md" "$STAGE/$APP_ID/CHANGELOG.de.md"
[[ -f "$ROOT/CHANGELOG.fr.md" ]] && cp "$ROOT/CHANGELOG.fr.md" "$STAGE/$APP_ID/CHANGELOG.fr.md"
[[ -f "$ROOT/LICENSE" ]] && cp "$ROOT/LICENSE" "$STAGE/$APP_ID/LICENSE"
[[ -f "$ROOT/README.md" ]] && cp "$ROOT/README.md" "$STAGE/$APP_ID/README.md"

mkdir -p "$OUT_DIR"
ARCHIVE="$OUT_DIR/${APP_ID}-${VERSION}.tar.gz"
tar --numeric-owner --owner=0 --group=0 -czf "$ARCHIVE" -C "$STAGE" "$APP_ID"
echo "built: $ARCHIVE"

if [[ ! -f "$KEY" ]]; then
  echo "note: signing key not found at $KEY" >&2
  echo "      set NC_SIGN_KEY or place the key, then re-run to get the signature" >&2
  exit 0
fi

SIG="$(openssl dgst -sha512 -sign "$KEY" "$ARCHIVE" | openssl base64 -A)"
echo
echo "base64 SHA-512 signature over the LOCAL archive (diagnosis only):"
echo "$SIG"
echo
echo "note: do NOT submit this signature. The store checks the bytes it downloads," >&2
echo "      and tar.gz is not byte reproducible. Sign the downloaded release asset" >&2
echo "      instead (docs/store-submission.md, runbook step 6)." >&2
