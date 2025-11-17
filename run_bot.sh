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

# One-time setup for venv
if [[ ! -d .venv ]]; then
  echo "[setup] Creating venv and installing requirements..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip -q install --upgrade pip
  pip -q install -r requirements.txt
else
  source .venv/bin/activate
fi

# Ensure Playwright browser is installed for this user and path
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$PWD/.pw-browsers}"
echo "[setup] Ensuring Playwright Chromium at $PLAYWRIGHT_BROWSERS_PATH ..."
python -m playwright install chromium || true

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
