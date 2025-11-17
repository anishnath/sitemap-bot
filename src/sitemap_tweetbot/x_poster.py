import os
import time
from pathlib import Path
from typing import Optional, Tuple

import tweepy


class XAuthError(Exception):
    pass


def _get_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise XAuthError(f"Missing env: {name}")
    return v


def get_twitter_api() -> tweepy.API:
    """Create a Tweepy API client for v1.1 endpoints (media + status)."""
    api_key = _get_env('TWITTER_API_KEY')
    api_secret = _get_env('TWITTER_API_SECRET')
    access_token = _get_env('TWITTER_ACCESS_TOKEN')
    access_secret = _get_env('TWITTER_ACCESS_SECRET')

    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
    api = tweepy.API(auth)
    # Quick sanity call (rate-limited); do not fail hard
    try:
        api.verify_credentials()
    except Exception:
        pass
    return api


def get_twitter_client() -> tweepy.Client:
    """Create a Tweepy v2 Client in user context for creating tweets."""
    bearer = _get_env('TWITTER_BEARER_TOKEN')
    api_key = _get_env('TWITTER_API_KEY')
    api_secret = _get_env('TWITTER_API_SECRET')
    access_token = _get_env('TWITTER_ACCESS_TOKEN')
    access_secret = _get_env('TWITTER_ACCESS_SECRET')

    client = tweepy.Client(
        bearer_token=bearer,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    return client


def post_tweet_with_media_v1(
    text: str,
    image_path: Path,
    alt_text: Optional[str] = None,
    dry_run: bool = False,
) -> Tuple[Optional[str], Optional[str]]:
    """Post a tweet with a media image.

    Returns: (tweet_id_str, tweet_url) or (None, None) on dry_run.
    Requires env vars: TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET.
    To reduce accidental posts, also requires TWITTER_POST=1 unless dry_run=True.
    """
    if dry_run:
        return None, None

    if os.getenv('TWITTER_POST') not in ('1', 'true', 'TRUE', 'yes', 'YES'):
        raise XAuthError("Set TWITTER_POST=1 to enable live posting.")

    api = get_twitter_api()

    media = api.media_upload(filename=str(image_path))
    if alt_text:
        # best-effort alt text
        alt = alt_text.strip()
        if alt:
            try:
                api.create_media_metadata(media.media_id, alt)
            except Exception:
                pass

    status = api.update_status(status=text, media_ids=[media.media_id])
    tweet_id = status.id_str
    try:
        user = api.verify_credentials()
        screen_name = getattr(user, 'screen_name', None)
    except Exception:
        screen_name = None
    url = f"https://x.com/{screen_name}/status/{tweet_id}" if screen_name else None
    return tweet_id, url


def post_tweet_with_media_v2(
    text: str,
    image_path: Path,
    alt_text: Optional[str] = None,
    dry_run: bool = False,
) -> Tuple[Optional[str], Optional[str]]:
    """Post a tweet using v2 create tweet, uploading media via v1.1.

    Requires TWITTER_BEARER_TOKEN in addition to v1.1 keys. Also requires TWITTER_POST=1.
    """
    if dry_run:
        return None, None

    if os.getenv('TWITTER_POST') not in ('1', 'true', 'TRUE', 'yes', 'YES'):
        raise XAuthError("Set TWITTER_POST=1 to enable live posting.")

    # Upload media via v1.1
    api = get_twitter_api()
    media = api.media_upload(filename=str(image_path))
    if alt_text:
        alt = alt_text.strip()
        if alt:
            try:
                api.create_media_metadata(media.media_id, alt)
            except Exception:
                pass

    # Create tweet via v2
    client = get_twitter_client()
    resp = client.create_tweet(text=text, media_ids=[media.media_id])
    tweet_id = str(resp.data.get('id')) if resp and resp.data else None
    screen_name = None
    try:
        me = client.get_me()
        if me and me.data:
            screen_name = getattr(me.data, 'username', None)
    except Exception:
        pass
    url = f"https://x.com/{screen_name}/status/{tweet_id}" if screen_name and tweet_id else None
    return tweet_id, url
