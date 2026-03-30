#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-main}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Project dir: ${PROJECT_DIR}"
cd "${PROJECT_DIR}"

echo "==> Fetching latest changes from origin/${BRANCH}"
git fetch origin "${BRANCH}"
git checkout "${BRANCH}"
git pull --ff-only origin "${BRANCH}"

echo "==> Rebuilding and restarting containers"
docker compose up -d --build --remove-orphans

echo "==> Deployment finished successfully"
docker compose ps
