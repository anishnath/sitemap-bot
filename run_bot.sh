#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Load environment from .env if present (do not commit .env)
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# One-time setup for venv and browsers
if [[ ! -d .venv ]]; then
  echo "[setup] Creating venv and installing requirements..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip -q install --upgrade pip
  pip -q install -r requirements.txt
  echo "[setup] Installing Playwright Chromium..."
  # Install browser binaries; ignore error if already installed
  python -m playwright install chromium || true
else
  source .venv/bin/activate
fi

# Prevent overlapping runs using flock
LOCKFILE="/tmp/sitemap-tweetbot.lock"
(
  flock -n 9 || { echo "Another run is in progress; exiting"; exit 0; }
  echo "[run] Generating and posting 1 tweet..."
  python -m src.sitemap_tweetbot.main \
    --sitemap sitemap.xml \
    --count 1 \
    --out outputs \
    --exclude-patterns "/docs/" \
    --wait-until domcontentloaded \
    --timeout 60000 \
    --block-ads \
    --use-openai \
    --hashtag-strategy popular \
    --post-to-x
) 9>"$LOCKFILE"

echo "[done]"
