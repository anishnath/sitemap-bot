import argparse
import time
import random
import sys
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .tweetgen import compose_tweet
from .screenshot import take_screenshot, DEFAULT_VIEWPORT, AD_HOST_PATTERNS
from .openai_gen import generate_tweet_openai, DEFAULT_MODEL as OPENAI_DEFAULT_MODEL
from .x_poster import (
    post_tweet_with_media_v2,
    post_tweet_with_media_v1,
    post_text_v2,
    post_text_v1,
    XAuthError,
)


def read_sitemap(path: Path):
    tree = ET.parse(str(path))
    root = tree.getroot()
    # namespaces optional; handle default
    urls = []
    for loc in root.iter():
        if loc.tag.endswith('loc') and loc.text:
            urls.append(loc.text.strip())
    return urls


def extract_meta_from_page(url: str, timeout_ms: int = 30000, wait_until: str = 'domcontentloaded', block_ads: bool = True):
    meta = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': DEFAULT_VIEWPORT[0], 'height': DEFAULT_VIEWPORT[1]})
        page = context.new_page()
        if block_ads:
            def _route(route):
                u = route.request.url
                if any(pat in u for pat in AD_HOST_PATTERNS):
                    return route.abort()
                return route.continue_()
            context.route("**/*", _route)
        # more tolerant load sequence
        try:
            page.goto(url, wait_until=wait_until, timeout=timeout_ms)
        except Exception:
            try:
                page.goto(url, wait_until='load', timeout=int(timeout_ms*1.5))
            except Exception:
                page.goto(url, wait_until='domcontentloaded', timeout=int(timeout_ms*2))
        html = page.content()
        context.close()
        browser.close()
    soup = BeautifulSoup(html, 'lxml')
    def get(name, attr='name'):
        tag = soup.find('meta', {attr: name})
        return (tag.get('content') or '').strip() if tag and tag.has_attr('content') else ''
    # collect several common fields
    meta['title'] = (soup.title.string.strip() if soup.title and soup.title.string else '')
    meta['og:title'] = get('og:title', 'property')
    meta['description'] = get('description')
    meta['og:description'] = get('og:description', 'property')
    meta['keywords'] = get('keywords')
    return meta


def main():
    ap = argparse.ArgumentParser(description='Generate tweet copy + screenshots from a sitemap.xml')
    ap.add_argument('--sitemap', type=Path, default=Path('sitemap.xml'))
    ap.add_argument('--count', type=int, default=2)
    ap.add_argument('--out', type=Path, default=Path('outputs'))
    ap.add_argument('--exclude-patterns', type=str, default='/docs/', help='Comma-separated substrings; URLs containing any will be skipped (case-insensitive)')
    ap.add_argument('--width', type=int, default=DEFAULT_VIEWPORT[0])
    ap.add_argument('--height', type=int, default=DEFAULT_VIEWPORT[1])
    ap.add_argument('--timeout', type=int, default=30000)
    ap.add_argument('--wait-until', type=str, default='domcontentloaded', choices=['domcontentloaded','load','networkidle'], help='Playwright wait target for navigation')
    ap.add_argument('--block-ads', dest='block_ads', action='store_true', default=True, help='Block requests to common ad hosts and hide ad containers')
    ap.add_argument('--no-block-ads', dest='block_ads', action='store_false')
    # OpenAI options
    ap.add_argument('--use-openai', action='store_true', help='Use OpenAI to generate tweet copy')
    ap.add_argument('--openai-model', type=str, default=OPENAI_DEFAULT_MODEL)
    ap.add_argument('--tone', type=str, default='helpful, confident, concise')
    ap.add_argument('--brand', type=str, default='')
    ap.add_argument('--hashtags', type=str, default='', help='Comma-separated list of preferred hashtags')
    ap.add_argument('--hashtag-strategy', type=str, default='auto', choices=['auto','popular','input'], help='OpenAI hashtag strategy: popular=relevant high-reach only; input=use --hashtags only; auto=mix popular + derived')
    ap.add_argument('--cta', type=str, default='Try it')
    # X/Twitter posting
    ap.add_argument('--post-to-x', action='store_true', help='Post tweets to X via API (requires env and TWITTER_POST=1)')
    ap.add_argument('--x-wait-seconds', type=int, default=2, help='Delay between posts to avoid rate limits')
    ap.add_argument('--x-no-alt', dest='x_use_alt', action='store_false', default=True, help='Do not attach alt text to media')
    args = ap.parse_args()

    if not args.sitemap.exists():
        print(f"Sitemap not found: {args.sitemap}", file=sys.stderr)
        sys.exit(1)

    urls = read_sitemap(args.sitemap)
    if not urls:
        print('No URLs found in sitemap', file=sys.stderr)
        sys.exit(2)

    # filter excluded patterns
    patterns = [p.strip().lower() for p in (args.exclude_patterns or '').split(',') if p.strip()]
    if patterns:
        urls = [u for u in urls if all(p not in u.lower() for p in patterns)]

    if not urls:
        print('No URLs remain after applying exclude patterns', file=sys.stderr)
        sys.exit(3)

    pick = random.sample(urls, k=min(args.count, len(urls)))

    args.out.mkdir(parents=True, exist_ok=True)
    results = []

    for url in pick:
        print(f"Processing: {url}")
        shot_path = ''
        try:
            shot = take_screenshot(
                url,
                args.out,
                viewport=(args.width, args.height),
                timeout_ms=args.timeout,
                wait_until=args.wait_until,
                block_ads=args.block_ads,
            )
            shot_path = str(shot)
        except Exception as e:
            print(f"  Screenshot failed: {e}", file=sys.stderr)

        meta = {}
        try:
            meta = extract_meta_from_page(url, timeout_ms=args.timeout, wait_until=args.wait_until, block_ads=args.block_ads)
        except Exception as e:
            print(f"  Meta extract failed: {e}", file=sys.stderr)

        # Decide generator
        tweet = ''
        if args.use_openai:
            try:
                tags = [t.strip() for t in (args.hashtags or '').split(',') if t.strip()]
                tweet = generate_tweet_openai(
                    meta=meta,
                    url=url,
                    model=args.openai_model,
                    tone=args.tone,
                    brand=(args.brand or None),
                    hashtags=(tags or None),
                    cta=args.cta,
                    hashtag_strategy=args.hashtag_strategy,
                )
                source = 'openai'
            except Exception as e:
                print(f"  OpenAI generation failed: {e}. Falling back to local generator.", file=sys.stderr)
                tweet = compose_tweet(meta, url)
                source = 'local'
        else:
            tweet = compose_tweet(meta, url)
            source = 'local'

        record = {
            'url': url,
            'image': shot_path,
            'tweet': tweet,
            'generated_by': source,
            'meta': meta,
        }

        # Optional: post to X
        if args.post_to_x:
            try:
                alt_text = None
                if args.x_use_alt:
                    # derive a short alt text from meta
                    t = meta.get('og:title') or meta.get('title') or ''
                    d = meta.get('og:description') or meta.get('description') or ''
                    alt_text = (t or d)[:420]
                tweet_id = tweet_url = None
                if shot_path and Path(shot_path).is_file():
                    # Prefer v2 post with media; fall back to v1.1
                    try:
                        tweet_id, tweet_url = post_tweet_with_media_v2(tweet, Path(shot_path), alt_text=alt_text, dry_run=False)
                    except Exception as e_v2:
                        print(f"  v2 post failed: {e_v2}. Trying v1.1...", file=sys.stderr)
                        tweet_id, tweet_url = post_tweet_with_media_v1(tweet, Path(shot_path), alt_text=alt_text, dry_run=False)
                else:
                    # Text-only fallback
                    try:
                        tweet_id, tweet_url = post_text_v2(tweet, dry_run=False)
                    except Exception as e_v2:
                        print(f"  v2 text post failed: {e_v2}. Trying v1.1...", file=sys.stderr)
                        tweet_id, tweet_url = post_text_v1(tweet, dry_run=False)
                record['x_tweet_id'] = tweet_id
                record['x_url'] = tweet_url
                if args.x_wait_seconds:
                    time.sleep(args.x_wait_seconds)
            except XAuthError as e:
                print(f"  X posting skipped: {e}", file=sys.stderr)
            except Exception as e:
                print(f"  X posting failed: {e}", file=sys.stderr)

        results.append(record)

    # write outputs
    (args.out / 'posts.json').write_text(json.dumps(results, indent=2))
    with (args.out / 'posts.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['url', 'image', 'tweet'])
        for r in results:
            w.writerow([r['url'], r['image'], r['tweet']])

    # nice markdown for manual posting
    lines = []
    for r in results:
        lines.append(f"- URL: {r['url']}")
        lines.append(f"  Image: {r['image']}")
        lines.append(f"  Tweet: {r['tweet']}")
        lines.append("")
    (args.out / 'posts.md').write_text('\n'.join(lines))

    print(f"Done. Wrote: {args.out/'posts.json'}, {args.out/'posts.csv'}, {args.out/'posts.md'}")


if __name__ == '__main__':
    main()
