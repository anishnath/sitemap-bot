#!/usr/bin/env bash
set -euo pipefail

# Simple bootstrap + run script to post tweets with images to X
# - Creates/uses a Python venv
# - Installs requirements and Playwright browser
# - Validates X API env vars
# - Runs the sitemap tweetbot with sensible defaults

usage() {
  cat <<'USAGE'
Usage: ./post_to_x.sh [options]

Options (defaults shown):
  --count N                  Number of URLs to pick (default: 2)
  --out DIR                  Output directory (default: outputs)
  --sitemap PATH             Path to sitemap.xml (default: sitemap.xml)
  --exclude PATTERNS         Comma-separated URL substrings to skip (default: /docs/)
  --timeout MS               Navigation timeout in ms (default: 60000)
  --wait-until VAL           domcontentloaded|load|networkidle (default: domcontentloaded)
  --aspect twitter|card      1200x675 (twitter) or 1200x628 (card) (default: twitter)
  --no-openai                Disable OpenAI; use local generator
  --openai-model MODEL       OpenAI model (default: gpt-4o-mini)
  --tone STR                 Tone (default: "helpful, confident, concise")
  --brand STR                Brand name (default: empty)
  --hashtags TAGS            Comma-separated hashtags
  --hashtag-strategy STR     popular|auto|input (default: popular)
  --no-block-ads             Disable ad blocking
  --dry-run                  Run everything but do not post to X
  -h|--help                  Show this help

Requires environment variables for X posting:
  TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET,
  TWITTER_BEARER_TOKEN, and TWITTER_POST=1 (safety switch). If --dry-run is used,
  posting is skipped and these are not required.

OpenAI (optional): set OPENAI_API_KEY to enable --use-openai mode.
USAGE
}

COUNT=2
OUT_DIR="outputs"
SITEMAP="sitemap.xml"
EXCLUDE="/docs/"
TIMEOUT=60000
WAIT_UNTIL="domcontentloaded"
WIDTH=1200
HEIGHT=675 # twitter single image 16:9
USE_OPENAI=1
OPENAI_MODEL="gpt-4o-mini"
TONE="helpful, confident, concise"
BRAND=""
HASHTAGS=""
HASHTAG_STRATEGY="popular"
BLOCK_ADS=1
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --count) COUNT="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --sitemap) SITEMAP="$2"; shift 2 ;;
    --exclude) EXCLUDE="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --wait-until) WAIT_UNTIL="$2"; shift 2 ;;
    --aspect)
      if [[ "$2" == "card" ]]; then WIDTH=1200; HEIGHT=628; else WIDTH=1200; HEIGHT=675; fi
      shift 2 ;;
    --no-openai) USE_OPENAI=0; shift ;;
    --openai-model) OPENAI_MODEL="$2"; shift 2 ;;
    --tone) TONE="$2"; shift 2 ;;
    --brand) BRAND="$2"; shift 2 ;;
    --hashtags) HASHTAGS="$2"; shift 2 ;;
    --hashtag-strategy) HASHTAG_STRATEGY="$2"; shift 2 ;;
    --no-block-ads) BLOCK_ADS=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 2 ;;
  esac
done

cd "$(dirname "$0")"

# Load .env if present for convenience
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ ! -f "$SITEMAP" ]]; then
  echo "ERROR: sitemap not found at $SITEMAP" >&2
  exit 1
fi

# Setup venv
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip -q install --upgrade pip
pip -q install -r requirements.txt

# Playwright browser (idempotent)
python -m playwright install chromium || true

# Validate X env if not dry run
if [[ "$DRY_RUN" -eq 0 ]]; then
  REQ=(TWITTER_API_KEY TWITTER_API_SECRET TWITTER_ACCESS_TOKEN TWITTER_ACCESS_SECRET TWITTER_BEARER_TOKEN TWITTER_POST)
  for v in "${REQ[@]}"; do
    if [[ -z "${!v:-}" ]]; then
      echo "ERROR: Missing env $v (set TWITTER_POST=1 to enable posting)" >&2
      exit 3
    fi
  done
fi

USE_OAI_FLAG=()
if [[ "$USE_OPENAI" -eq 1 ]]; then
  if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    USE_OAI_FLAG=(--use-openai --openai-model "$OPENAI_MODEL" --tone "$TONE" --brand "$BRAND" --hashtag-strategy "$HASHTAG_STRATEGY")
    if [[ -n "$HASHTAGS" ]]; then
      USE_OAI_FLAG+=(--hashtags "$HASHTAGS")
    fi
  else
    echo "WARN: OPENAI_API_KEY not set; falling back to local copy generator" >&2
  fi
fi

POST_FLAGS=(--post-to-x)
if [[ "$DRY_RUN" -eq 1 ]]; then
  POST_FLAGS=() # skip posting
fi

BLOCK_FLAG=(--block-ads)
if [[ "$BLOCK_ADS" -eq 0 ]]; then
  BLOCK_FLAG=(--no-block-ads)
fi

python -m src.sitemap_tweetbot.main \
  --sitemap "$SITEMAP" \
  --count "$COUNT" \
  --out "$OUT_DIR" \
  --exclude-patterns "$EXCLUDE" \
  --timeout "$TIMEOUT" \
  --wait-until "$WAIT_UNTIL" \
  --width "$WIDTH" \
  --height "$HEIGHT" \
  "${BLOCK_FLAG[@]}" \
  "${USE_OAI_FLAG[@]}" \
  "${POST_FLAGS[@]}"

echo "Done. Check $OUT_DIR for posts and images."
