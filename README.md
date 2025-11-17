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
 - If you see Playwright timeouts, try `--wait-until domcontentloaded` or increase `--timeout`.
