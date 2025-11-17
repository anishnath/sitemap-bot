import re
from typing import List, Dict

MAX_LEN = 280

_EMOJI = "⚡️"

COMMON_HASHTAGS = {
    'crypto': '#crypto', 'cryptography': '#cryptography', 'security': '#security', 'privacy': '#privacy',
    'ssl': '#ssl', 'tls': '#tls', 'certificate': '#PKI', 'pki': '#PKI', 'ssl/tls': '#TLS',
    'electronics': '#electronics', 'circuits': '#circuits', 'ee': '#EE', 'stem': '#STEM',
    'makers': '#makers', 'developer': '#devtools', 'tools': '#tools', 'calculator': '#calculator',
}

STOPWORDS = set('a an and the for to of with in on at from by your our you we us is are this that it as be or if into about using make get free new'.split())


def _slugify(text: str) -> str:
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', text).strip().lower()
    text = re.sub(r'\s+', '-', text)
    return text[:60]


def derive_hashtags(meta_keywords: List[str], title: str) -> List[str]:
    tags = []
    seen = set()
    # from meta keywords first
    for kw in meta_keywords:
        for token in re.split(r'[\s/,-]+', kw.lower()):
            token = token.strip()
            if not token or token in STOPWORDS:
                continue
            tag = COMMON_HASHTAGS.get(token) or f"#{re.sub(r'[^a-z0-9]+','', token)}"
            if len(tag) > 1 and tag not in seen:
                seen.add(tag)
                tags.append(tag)
            if len(tags) >= 3:
                return tags
    # fallback to title words
    for token in re.findall(r"[A-Za-z0-9]+", title.lower()):
        if token in STOPWORDS or len(token) < 3:
            continue
        tag = COMMON_HASHTAGS.get(token) or f"#{token}"
        if tag not in seen:
            seen.add(tag)
            tags.append(tag)
        if len(tags) >= 3:
            break
    return tags[:3]


def compose_tweet(meta: Dict[str, str], url: str) -> str:
    title = meta.get('og:title') or meta.get('title') or 'Check this out'
    desc = meta.get('og:description') or meta.get('description') or ''
    keywords = [k.strip() for k in (meta.get('keywords') or '').split(',') if k.strip()]

    hashtags = derive_hashtags(keywords, title)
    cta = 'Try it' if any(x in title.lower() for x in ['calculator', 'tool', 'generator']) else 'Learn more'

    base = f"{_EMOJI} {title}."
    if desc:
        base += f" {desc}"

    parts = [base.strip()]
    if url:
        parts.append(url)
    if hashtags:
        parts.append(' '.join(hashtags[:3]))
    parts.append(cta)

    tweet = ' '.join(p for p in parts if p)

    # Trim to 280 chars without cutting URL
    if len(tweet) > MAX_LEN and url in tweet:
        # reserve url length + space
        reserve = len(url) + 1
        before_url, after_url = tweet.split(url, 1)
        head = before_url.strip()
        tail = after_url.strip()
        # trim head first
        head = head[: MAX_LEN - reserve - len(tail) - 1].rstrip()
        tweet = f"{head} {url} {tail}".strip()

    if len(tweet) > MAX_LEN:
        tweet = tweet[:MAX_LEN].rstrip()

    return tweet

