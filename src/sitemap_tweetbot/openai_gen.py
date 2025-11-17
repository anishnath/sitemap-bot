import os
from typing import Dict, List, Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


DEFAULT_MODEL = "gpt-4o-mini"

# Curated, higher-reach but still relevant hashtag bundles
POPULAR_TAGS = {
    'security': ['#Cybersecurity', '#InfoSec', '#PKI', '#TLS', '#AppSec'],
    'crypto': ['#Crypto', '#Cryptography', '#Encryption'],
    'dev': ['#Developers', '#DevTools', '#OpenSource'],
    'electronics': ['#Electronics', '#STEM', '#Engineering'],
    'math': ['#Math', '#STEM', '#Education'],
    'physics': ['#Physics', '#STEM', '#Science'],
    'chemistry': ['#Chemistry', '#STEM', '#Science'],
    'pdf': ['#PDF', '#Productivity', '#Docs'],
    'video': ['#VideoEditing', '#ContentCreation', '#Video'],
    'devops': ['#DevOps', '#Kubernetes', '#SRE'],
    'network': ['#Networking', '#NetworkEngineering', '#SysAdmin'],
    'encoders': ['#Encoding', '#Decoding', '#DataFormats'],
    'finance': ['#Finance', '#FinTech', '#Investing'],
    'health': ['#HealthTech', '#Healthcare', '#MedTech'],
    'general': ['#Tech', '#Learn', '#Tools'],
}


def _choose_buckets(title: str, keywords: str) -> List[str]:
    text = f"{title} {keywords}".lower()
    buckets = []
    def add(b):
        if b not in buckets:
            buckets.append(b)
    if any(k in text for k in ['ssl', 'tls', 'pki', 'certificate', 'cert', 'jwt', 'jws', 'security', 'infosec', 'cve']):
        add('security'); add('crypto')
    if any(k in text for k in ['crypto', 'cryptography', 'hash', 'aes', 'rsa']):
        add('crypto')
    if any(k in text for k in ['developer', 'tool', 'api', 'cli', 'generator', 'calculator']):
        add('dev')
    if any(k in text for k in ['ohm', 'resistor', 'circuit', 'voltage', 'current', 'electronics']):
        add('electronics')
    if any(k in text for k in ['mean', 'median', 'mode', 'probability', 'equation', 'math', 'algebra', 'calculus']):
        add('math')
    if any(k in text for k in ['physics', 'mechanics', 'projectile', 'kinematics', 'motion', 'energy']):
        add('physics')
    if any(k in text for k in ['chemistry', 'chemical', 'stoichiometry', 'periodic', 'molecule', 'reaction']):
        add('chemistry')
    if any(k in text for k in ['pdf', 'document', 'merge pdf', 'split pdf', 'compress pdf', 'extract pdf']):
        add('pdf')
    if any(k in text for k in ['video', 'ffmpeg', 'codec', 'transcode', 'edit video', 'gif']):
        add('video')
    if any(k in text for k in ['devops', 'docker', 'kubernetes', 'k8s', 'helm', 'ci', 'cd', 'pipeline', 'terraform']):
        add('devops')
    if any(k in text for k in ['network', 'ip', 'dns', 'ping', 'traceroute', 'whois', 'subnet', 'cidr']):
        add('network')
    if any(k in text for k in ['encode', 'decoder', 'encoding', 'base64', 'urlencode', 'hex', 'ascii', 'qrcode']):
        add('encoders')
    if any(k in text for k in ['finance', 'loan', 'interest', 'mortgage', 'npv', 'roi', 'stock', 'investment']):
        add('finance')
    if any(k in text for k in ['health', 'bmi', 'calorie', 'nutrition', 'fitness', 'heart']):
        add('health')
    if not buckets:
        add('general')
    return buckets


def _build_hashtags(keywords: str, explicit_tags: Optional[List[str]], title: str, strategy: str) -> List[str]:
    # explicit user-provided
    if explicit_tags:
        return [t.strip() for t in explicit_tags if t.strip()][:6]

    tags: List[str] = []
    seen = set()

    if strategy in ('popular', 'auto'):
        for b in _choose_buckets(title, keywords):
            for h in POPULAR_TAGS.get(b, []):
                if h.lower() not in seen:
                    seen.add(h.lower())
                    tags.append(h)
                if len(tags) >= 6:
                    break
            if len(tags) >= 6:
                break

    if strategy == 'auto' and len(tags) < 6:
        # augment with derived from keywords
        toks = [t.strip() for t in (keywords or '').split(',') if t.strip()]
        for t in toks:
            h = '#' + ''.join(ch for ch in t if ch.isalnum())
            if len(h) > 1 and h.lower() not in seen:
                seen.add(h.lower())
                tags.append(h)
            if len(tags) >= 6:
                break

    return tags[:6]


def generate_tweet_openai(
    meta: Dict[str, str],
    url: str,
    model: str = DEFAULT_MODEL,
    tone: str = "helpful, confident, concise",
    brand: Optional[str] = None,
    hashtags: Optional[List[str]] = None,
    cta: str = "Try it",
    temperature: float = 0.7,
    max_tokens: int = 120,
    hashtag_strategy: str = 'auto',  # 'auto' | 'popular' | 'input'
) -> str:
    """Use OpenAI to create a single tweet (<=280 chars).

    Requires OPENAI_API_KEY in environment. Falls back by raising if unavailable.
    """
    if OpenAI is None:
        raise RuntimeError("openai package not available. Install dependencies.")
    if not os.getenv('OPENAI_API_KEY'):
        raise RuntimeError("OPENAI_API_KEY not set in environment.")

    client = OpenAI()

    title = meta.get('og:title') or meta.get('title') or ''
    desc = meta.get('og:description') or meta.get('description') or ''
    keywords = meta.get('keywords') or ''
    tags_pool = _build_hashtags(keywords, hashtags, title, hashtag_strategy)
    brand_line = f"Brand voice: {brand}." if brand else ""

    system = (
        "You are a social media copywriter for technical audiences. "
        "Write accurate, concise posts without clickbait."
    )
    user = f"""
Create 1 X/Twitter post (<=280 chars) for this page.
Constraints:
- Include this URL: {url}
- Use at most 1 emoji.
- Include 2–3 hashtags from this list only: {', '.join(tags_pool) if tags_pool else '(derive from content)'}
- Clear benefit + a crisp CTA (e.g., '{cta}').
- Tone: {tone}. {brand_line}

Page data:
- Title: {title}
- Description: {desc}
- Keywords: {keywords}

Output: just the tweet text, nothing else.
"""

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    text = resp.choices[0].message.content.strip()
    return text
