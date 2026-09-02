#!/usr/bin/env bash
set -euo pipefail

: "${FORGEJO_URL:?FORGEJO_URL is required}"
: "${FORGEJO_REPOSITORY:?FORGEJO_REPOSITORY is required}"
: "${FORGEJO_TOKEN:?FORGEJO_TOKEN is required}"

GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-destinorandagio/cryptoaidsupport}"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

SOURCE_URL="https://github.com/${GITHUB_REPOSITORY}.git"
TARGET_BASE="${FORGEJO_URL%/}"
TARGET_URL="${TARGET_BASE/https:\/\//https:\/\/${FORGEJO_TOKEN}@}"
TARGET_URL="${TARGET_URL/http:\/\//http:\/\/${FORGEJO_TOKEN}@}/${FORGEJO_REPOSITORY}.git"

echo "Mirroring ${GITHUB_REPOSITORY} to Forgejo ${FORGEJO_REPOSITORY}"
git clone --mirror "$SOURCE_URL" "$WORKDIR/repo.git"
git -C "$WORKDIR/repo.git" push --mirror "$TARGET_URL"
echo "Forgejo mirror complete"
