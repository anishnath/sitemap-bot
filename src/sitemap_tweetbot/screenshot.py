from typing import Tuple
from pathlib import Path
from urllib.parse import urlparse
import time

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout


DEFAULT_VIEWPORT = (1200, 675)  # 16:9, good for Twitter


def sanitize_filename(url: str) -> str:
    p = urlparse(url)
    safe = (p.netloc + p.path).replace('/', '_').strip('_')
    if not safe:
        safe = 'page'
    return safe[:150]


AD_HOST_PATTERNS = [
    # Ads
    'googlesyndication.com',
    'googleads.g.doubleclick.net',
    'doubleclick.net',
    'adservice.google.com',
    'googletagservices.com',
    'googletagmanager.com',  # includes gtm.js and gtag
    'adsystem.com',
    'taboola.com',
    'outbrain.com',
    # Analytics / trackers
    'google-analytics.com',
    'analytics.google.com',
    'ssl.google-analytics.com',
    'stats.g.doubleclick.net',
    'statcounter.com',
    'sc-static.net',
    'c.statcounter.com',
]


def take_screenshot(
    url: str,
    out_dir: Path,
    viewport: Tuple[int, int] = DEFAULT_VIEWPORT,
    timeout_ms: int = 30000,
    wait_until: str = 'domcontentloaded',
    block_ads: bool = True,
) -> Path:
    """Navigate to URL and take a 16:9 screenshot.

    Robust to slow pages by falling back through lighter wait states.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = sanitize_filename(url) + '.png'
    out_path = out_dir / fname

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': viewport[0], 'height': viewport[1]},
            ignore_https_errors=True,
        )
        page = context.new_page()

        if block_ads:
            def _route(route):
                url = route.request.url
                if any(pat in url for pat in AD_HOST_PATTERNS):
                    return route.abort()
                return route.continue_()
            context.route("**/*", _route)

        # Try increasingly lenient waits
        tried = []
        for wu, to in [
            (wait_until, timeout_ms),
            ('load', int(timeout_ms * 1.5)),
            ('domcontentloaded', int(timeout_ms * 2)),
        ]:
            try:
                page.goto(url, wait_until=wu, timeout=to)
                break
            except PwTimeout:
                tried.append(wu)
                continue

        # small settle time for animations and late resources
        try:
            page.wait_for_timeout(1500)
        except Exception:
            pass

        # Hide common ad containers (AdSense, GPT)
        if block_ads:
            try:
                page.add_style_tag(content='''
                    ins.adsbygoogle, iframe[src*="googlesyndication"],
                    [id^="google_ads_"], [id*="google_ads_iframe"],
                    [data-google-query-id], .carbonads, #carbonads,
                    .adslot, .ad-container, .adsbox { display: none !important; visibility: hidden !important; }
                ''')
            except Exception:
                pass

        # Even if navigation partially failed, try to capture what we have
        page.screenshot(path=str(out_path), full_page=False)

        context.close()
        browser.close()

    return out_path
