# sitemap-tweetbot

Generate tweet copy and screenshots from a `sitemap.xml`.

- Picks N random URLs from a sitemap
- Captures 16:9 screenshots suitable for X/Twitter
- Extracts page metadata and composes concise tweets with hashtags
- Outputs JSON/CSV/Markdown with tweet + image paths
 - Blocks common ad requests and hides ad containers by default (toggle with `--no-block-ads`)

## Setup

```bash
cd /Users/anish/git/sitemap-tweetbot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Usage

```bash
# Place sitemap.xml in project root (copied already) or pass --sitemap
# More tolerant navigation and skip docs pages:
python -m src.sitemap_tweetbot.main --count 2 --out outputs \
  --wait-until domcontentloaded --timeout 60000 \
  --exclude-patterns "/docs/" \
  --block-ads
```

Outputs are written to `outputs/`:
- `posts.json` – structured data (url, tweet, meta, image)
- `posts.csv` – quick import
- `posts.md` – human-friendly
- PNG screenshots in `outputs/`

## Notes
- The tool does not post to X/Twitter. It prepares copy and images for manual or API posting.
- Hashtags are derived from meta keywords/title; adjust `tweetgen.py` for your brand.
- Default viewport is `1200x675`.
- Ad/analytics blocking: Aborts requests to common ad and analytics hosts (e.g., `googlesyndication`, `doubleclick`, `googletagmanager`, `google-analytics.com`, `statcounter.com`) and injects CSS to hide Ad slots. Disable via `--no-block-ads`.

## OpenAI-Powered Copy (optional)

Enable OpenAI tweet generation instead of the local heuristic.

1. `export OPENAI_API_KEY=sk-...`
2. Run with flags:

```bash
python -m src.sitemap_tweetbot.main --count 2 --out outputs \
  --use-openai --openai-model gpt-4o-mini \
  --tone "helpful, confident, concise" \
  --brand "8gwifi" \
  --hashtags "#security,#crypto,#tools" \
  --hashtag-strategy popular \
  --cta "Try it"
```

If OpenAI fails or no key is set, the tool falls back to the local generator.

Hashtag strategies:
- `popular`: Use curated, higher-reach relevant hashtags only (preferred for discovery).
- `input`: Use only the tags you pass via `--hashtags`.
- `auto` (default): Mix curated popular tags with those derived from page keywords.

## Post directly to X (optional)

Requires X/Twitter API access. The tool prefers v2 `create tweet` and falls back to v1.1 if needed. Set env vars and enable posting.

Env vars required:
- For media upload (v1.1):
  - `TWITTER_API_KEY`
  - `TWITTER_API_SECRET`
  - `TWITTER_ACCESS_TOKEN`
  - `TWITTER_ACCESS_SECRET`
- For posting (v2 preferred):
  - `TWITTER_BEARER_TOKEN` (App bearer token, with write permissions on the project/app)
- Safety switch: `TWITTER_POST=1`

Run:
```bash
export TWITTER_API_KEY=...
export TWITTER_API_SECRET=...
export TWITTER_ACCESS_TOKEN=...
export TWITTER_ACCESS_SECRET=...
export TWITTER_POST=1  # required to actually post

python -m src.sitemap_tweetbot.main --count 2 --out outputs \
  --use-openai --post-to-x --x-wait-seconds 3
```

Notes:
- Media alt text is attached by default from page title/description. Disable with `--x-no-alt`.
- Posting uses v2 `create tweet` when possible (requires app with write access). If v2 fails, it tries v1.1 `statuses/update` (may require elevated/paid access).
- To avoid accidental posting, both `--post-to-x` and `TWITTER_POST=1` must be set.

## Server Deployment (Ubuntu + cron)

1) Install system deps (Playwright Chromium runtime) and git:

```bash
sudo apt-get update && sudo apt-get install -y \
  git python3-venv ca-certificates fonts-liberation \
  libasound2 libatk-bridge2.0-0 libatk1.0-0 libc6 libcairo2 libcups2 \
  libdbus-1-3 libdrm2 libexpat1 libfontconfig1 libgbm1 libgcc1 libglib2.0-0 \
  libgtk-3-0 libnspr4 libnss3 libpango-1.0-0 libstdc++6 libx11-6 libx11-xcb1 \
  libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 libxshmfence1 libxkbcommon0
```

2) Clone the repo:

```bash
cd ~ && git clone git@github.com:anishnath/sitemap-bot.git
cd sitemap-bot
```

3) Create `.env` with your secrets (do NOT commit):

```bash
cat > .env << 'ENV'
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...
TWITTER_BEARER_TOKEN=...
TWITTER_POST=1
OPENAI_API_KEY=...
ENV
chmod 600 .env
```

4) Test run once:

```bash
./run_bot.sh
```

5) Cron job every 2 hours:

```bash
(crontab -l 2>/dev/null; echo "0 */2 * * * cd $HOME/sitemap-bot && /bin/bash ./run_bot.sh >> $HOME/sitemap-bot/bot.log 2>&1") | crontab -
```

This posts 1 tweet per run with popular hashtags, OpenAI copy, and ad/analytics blocking.
 - If you see Playwright timeouts, try `--wait-until domcontentloaded` or increase `--timeout`.
