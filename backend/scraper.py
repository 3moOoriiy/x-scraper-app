# =============================================================
# X (Twitter) Posts Scraper - Guest Token + GraphQL
# Uses X's public guest token endpoint (no personal cookies needed)
# Completely free and reliable.
# =============================================================

import json
import html
import math
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

# =============================================================
# RATE LIMIT PROTECTION
# =============================================================
_RATE_LOCK = threading.Lock()
_LAST_REQUEST_TIME = 0.0
_MIN_DELAY_SEC = 0.3   # was 1.0 — X tolerates faster bursts with auth cookies

_CACHE = {}
_CACHE_TTL = 20                 # 20 sec — fresh counts for actively-growing tweets

_TWEETS_CACHE = {}
_TWEETS_CACHE_TTL = 20          # 20 sec
_TWEETS_CACHE_STALE_TTL = 3600  # 1 hour fallback during rate limits

_RATE_LIMIT_UNTIL = 0.0

# Guest token cache (X rotates these every ~3 hours)
_GUEST_TOKEN = None
_GUEST_TOKEN_AT = 0.0
_GUEST_TOKEN_TTL = 2 * 3600


def _throttle():
    global _LAST_REQUEST_TIME
    with _RATE_LOCK:
        elapsed = time.time() - _LAST_REQUEST_TIME
        if elapsed < _MIN_DELAY_SEC:
            time.sleep(_MIN_DELAY_SEC - elapsed)
        _LAST_REQUEST_TIME = time.time()


def _cache_get(key):
    entry = _CACHE.get(key)
    if not entry:
        return None
    ts, value = entry
    if time.time() - ts > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    return value


def _cache_set(key, value):
    _CACHE[key] = (time.time(), value)


# =============================================================
# CONFIG
# =============================================================
# Public bearer token (X web client - same for everyone, NOT personal)
BEARER_TOKEN = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
    "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

# Personal cookies (give higher rate limits than guest tokens)
import os

# Cookies are read from env vars in production (Render/Docker).
# Local fallback values are kept here for dev convenience.
AUTH_TOKEN = os.environ.get("X_AUTH_TOKEN") or "0f802daaf5b6b032fab9d010aae5c92e6b68610a"
CT0 = os.environ.get("X_CT0") or (
    "5cf3f97011e416d161513b34e310ec6f3869cef1beb6efbbcde7e520a5ad55b0"
    "88e3e24ab5359730161393b2f9f9dada22b914ac27baac885e6f8320627e7883bbc7f7dc53c075f82f66ca1045621ecb"
)

USER_BY_SCREEN_NAME_ID = "G3KGOASz96M-Qu0nwmGXNg"
USER_TWEETS_ID         = "E3opETHurmVJflFsUBVuUQ"
SEARCH_TIMELINE_ID     = "nK1dw4o2ttv4nlxoyKr_lQ"
TWEET_BY_REST_ID       = "0hWvDhmW8YQ-S_ib3azIrw"   # TweetResultByRestId — live engagement counts

GRAPHQL_BASE = "https://api.x.com/graphql"
DEFAULT_TIMEOUT = 30


def get_guest_token(force_refresh=False):
    """
    Fetch a guest token from X's public activation endpoint.
    No personal account needed - this is X's public mechanism.
    """
    global _GUEST_TOKEN, _GUEST_TOKEN_AT

    if not force_refresh and _GUEST_TOKEN:
        if time.time() - _GUEST_TOKEN_AT < _GUEST_TOKEN_TTL:
            return _GUEST_TOKEN

    try:
        r = requests.post(
            "https://api.x.com/1.1/guest/activate.json",
            headers={
                "Authorization": f"Bearer {BEARER_TOKEN}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/131.0.0.0 Safari/537.36",
            },
            timeout=15,
        )
        if r.status_code == 200:
            token = r.json().get("guest_token")
            if token:
                _GUEST_TOKEN = token
                _GUEST_TOKEN_AT = time.time()
                print(f"[Guest Token] Got new token: {token[:20]}...")
                return token
        else:
            print(f"[Guest Token] HTTP {r.status_code}")
    except Exception as e:
        print(f"[Guest Token] Error: {e}")
    return None


def build_session(use_guest=False):
    """
    Build a session - default uses personal cookies (higher rate limits).
    Pass use_guest=True for guest-token-only session as fallback.
    """
    s = requests.Session()
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://x.com",
        "Referer": "https://x.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/131.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
    }

    if use_guest:
        token = get_guest_token()
        headers["x-guest-token"] = token or ""
    else:
        # Use personal cookies (higher rate limits)
        headers["x-csrf-token"] = CT0
        headers["x-twitter-auth-type"] = "OAuth2Session"
        s.cookies.set("auth_token", AUTH_TOKEN, domain=".x.com")
        s.cookies.set("ct0", CT0, domain=".x.com")

    s.headers.update(headers)
    return s


# =============================================================
# DATE HELPERS
# =============================================================

def get_date_threshold(date_filter):
    now = datetime.now(timezone.utc)
    mapping = {
        "all":  None,
        "24h":  timedelta(hours=24),
        "3d":   timedelta(days=3),
        "7d":   timedelta(days=7),
        "30d":  timedelta(days=30),
        "90d":  timedelta(days=90),
        "180d": timedelta(days=180),
        "365d": timedelta(days=365),
    }
    delta = mapping.get(date_filter)
    return None if delta is None else now - delta


def get_date_range(specific_date=None, start_date=None, end_date=None):
    if specific_date:
        try:
            d = datetime.strptime(specific_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return d, d + timedelta(days=1) - timedelta(microseconds=1)
        except Exception:
            return None, None

    start = end = None
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) \
                  + timedelta(days=1) - timedelta(microseconds=1)
        except Exception:
            pass

    if start and end and start > end:
        s_day = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        e_day = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) \
                + timedelta(days=1) - timedelta(microseconds=1)
        return s_day, e_day

    return start, end


def parse_twitter_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
    except Exception:
        return None


def build_profile_url(username):
    return f"https://x.com/{username.strip().lstrip('@')}"


# =============================================================
# REQUEST with retry & token refresh
# =============================================================

def _do_request(session, url, params, max_attempts=3):
    global _RATE_LIMIT_UNTIL
    r = None
    for attempt in range(max_attempts):
        _throttle()
        try:
            r = session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        except Exception as e:
            if attempt < max_attempts - 1:
                time.sleep(1.5)
                continue
            return None, f"network: {e}"

        if r.status_code == 200:
            return r, None

        # Token expired or invalid -> refresh guest token
        if r.status_code in (401, 403) and attempt < max_attempts - 1:
            new_token = get_guest_token(force_refresh=True)
            if new_token:
                session.headers["x-guest-token"] = new_token
            time.sleep(1)
            continue

        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 0))
            if wait <= 0:
                wait = 4 if attempt == 0 else 8
            _RATE_LIMIT_UNTIL = time.time() + max(wait, 30)
            if attempt < max_attempts - 1:
                time.sleep(wait)
                # Try a fresh guest token after rate limit
                new_token = get_guest_token(force_refresh=True)
                if new_token:
                    session.headers["x-guest-token"] = new_token
                continue
            return r, "http_429"

        if r.status_code in (500, 502, 503, 504):
            if attempt < max_attempts - 1:
                time.sleep(1.5)
                continue

        return r, f"http_{r.status_code}"

    return r, f"http_{r.status_code if r else 'no_response'}"


# =============================================================
# GET USER ID
# =============================================================

def get_user_id(session, username):
    variables = {"screen_name": username, "withSafetyModeUserFields": True}
    features = {
        "hidden_profile_likes_enabled": True,
        "hidden_profile_subscriptions_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "subscriptions_verification_info_is_identity_verified_enabled": True,
        "subscriptions_verification_info_verified_since_enabled": True,
        "highlights_tweets_tab_ui_enabled": True,
        "responsive_web_twitter_article_notes_tab_enabled": True,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
    }
    fieldToggles = {"withAuxiliaryUserLabels": False}

    url = f"{GRAPHQL_BASE}/{USER_BY_SCREEN_NAME_ID}/UserByScreenName"
    params = {
        "variables": json.dumps(variables, separators=(",", ":")),
        "features":  json.dumps(features, separators=(",", ":")),
        "fieldToggles": json.dumps(fieldToggles, separators=(",", ":")),
    }

    r, err = _do_request(session, url, params)
    if err:
        return None, err

    try:
        data = r.json()
    except Exception:
        return None, "invalid_json"

    user = data.get("data", {}).get("user", {}).get("result", {})
    if not user:
        return None, "not_found"
    if user.get("__typename") == "UserUnavailable":
        reason = (user.get("reason") or "").lower()
        return None, "suspended" if "suspend" in reason else "unavailable"

    legacy = user.get("legacy", {}) or {}
    if legacy.get("protected"):
        return None, "protected"

    uid = user.get("rest_id") or user.get("id_str") or legacy.get("id_str")
    return uid, None


# =============================================================
# FETCH TWEETS
# =============================================================

def fetch_tweets_page(session, user_id, cursor=None, count=20):
    variables = {
        "userId": user_id,
        "count": count,
        "includePromotedContent": True,
        "withQuickPromoteEligibilityTweetFields": True,
        "withVoice": True,
        "withV2Timeline": True,
    }
    if cursor:
        variables["cursor"] = cursor

    features = {
        "rweb_tipjar_consumption_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "articles_preview_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "rweb_video_timestamps_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_enhance_cards_enabled": False,
    }
    fieldToggles = {"withArticlePlainText": False}

    url = f"{GRAPHQL_BASE}/{USER_TWEETS_ID}/UserTweets"
    params = {
        "variables": json.dumps(variables, separators=(",", ":")),
        "features":  json.dumps(features, separators=(",", ":")),
        "fieldToggles": json.dumps(fieldToggles, separators=(",", ":")),
    }

    r, err = _do_request(session, url, params)
    if err:
        return [], None, err

    try:
        data = r.json()
    except Exception:
        return [], None, "invalid_json"

    user = data.get("data", {}).get("user", {}).get("result", {})
    timeline = (
        user.get("timeline_v2", {}).get("timeline", {})
        or user.get("timeline", {}).get("timeline", {})
    )
    instructions = timeline.get("instructions", []) or []

    next_cursor = None
    for instr in instructions:
        if instr.get("type") in ("TimelineAddEntries", "TimelineReplaceEntry"):
            entries = instr.get("entries", []) or []
            if instr.get("entry"):
                entries = entries + [instr["entry"]]
            for e in entries:
                content = e.get("content", {})
                if content.get("cursorType") == "Bottom":
                    next_cursor = content.get("value")
                    break
        if next_cursor:
            break

    return instructions, next_cursor, None


# =============================================================
# SEARCH TWEETS (keyword / hashtag)
# =============================================================

def fetch_search_page(session, query, cursor=None, count=20, product="Latest"):
    """
    Hit X's SearchTimeline GraphQL endpoint.
    product: 'Top' | 'Latest' | 'People' | 'Photos' | 'Videos'
    """
    variables = {
        "rawQuery": query,
        "count": count,
        "querySource": "typed_query",
        "product": product,
    }
    if cursor:
        variables["cursor"] = cursor

    features = {
        "rweb_tipjar_consumption_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "articles_preview_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "rweb_video_timestamps_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_enhance_cards_enabled": False,
    }

    url = f"{GRAPHQL_BASE}/{SEARCH_TIMELINE_ID}/SearchTimeline"
    params = {
        "variables": json.dumps(variables, separators=(",", ":")),
        "features":  json.dumps(features, separators=(",", ":")),
    }

    r, err = _do_request(session, url, params)
    if err:
        return [], None, err
    try:
        data = r.json()
    except Exception:
        return [], None, "invalid_json"

    timeline = (data.get("data", {})
                .get("search_by_raw_query", {})
                .get("search_timeline", {})
                .get("timeline", {}))
    instructions = timeline.get("instructions", []) or []

    next_cursor = None
    for instr in instructions:
        if instr.get("type") in ("TimelineAddEntries", "TimelineReplaceEntry"):
            entries = instr.get("entries", []) or []
            if instr.get("entry"):
                entries = entries + [instr["entry"]]
            for e in entries:
                content = e.get("content", {})
                if content.get("cursorType") == "Bottom":
                    next_cursor = content.get("value")
                    break
        if next_cursor:
            break

    return instructions, next_cursor, None


# =============================================================
# PARSE TWEET
# =============================================================

def extract_tweet_data(tweet_result, username):
    try:
        if "result" in tweet_result:
            tweet_result = tweet_result["result"]
        if tweet_result.get("__typename") == "TweetWithVisibilityResults":
            tweet_result = tweet_result.get("tweet", {})

        legacy = tweet_result.get("legacy", {})
        if not legacy:
            return None

        core = tweet_result.get("core", {})
        user_result = (core.get("user_results", {}) or {}).get("result", {})
        user_legacy = user_result.get("legacy", {})
        author = (
            user_result.get("core", {}).get("screen_name")
            or user_legacy.get("screen_name", "")
        )

        # Skip replies always
        if legacy.get("in_reply_to_status_id_str") or legacy.get("in_reply_to_user_id_str"):
            return None

        # Determine post type
        is_retweet = bool(legacy.get("retweeted_status_result") or legacy.get("retweeted_status_id_str"))
        is_quote = bool(legacy.get("is_quote_status") or tweet_result.get("quoted_status_result"))

        # For retweets, author check is different (the retweeted_status_result has the original author)
        if not is_retweet:
            if author and author.lower() != username.lower():
                return None

        tweet_id = legacy.get("id_str", "")
        if not tweet_id:
            return None

        note_tweet = (
            tweet_result.get("note_tweet", {})
            .get("note_tweet_results", {})
            .get("result", {})
        )
        if note_tweet and note_tweet.get("text"):
            caption = note_tweet["text"]
        else:
            caption = legacy.get("full_text", "") or ""

        entities = legacy.get("entities", {})
        for ue in entities.get("urls", []) or []:
            short = ue.get("url", "")
            expanded = ue.get("expanded_url", "")
            if short and expanded:
                caption = caption.replace(short, expanded)

        media_list = entities.get("media", []) or []
        for m in media_list:
            short = m.get("url", "")
            if short and short in caption:
                caption = caption.replace(short, "")
        caption = html.unescape(caption.strip())

        image_urls = []
        video_urls = []
        has_video = False

        def _collect_media(media_arr):
            nonlocal has_video
            for m in (media_arr or []):
                mtype = m.get("type")
                url = m.get("media_url_https", "")
                if not url:
                    continue
                base = url.split("?")[0]
                hq = f"{base}?format=jpg&name=large"

                if mtype == "photo":
                    if hq not in image_urls:
                        image_urls.append(hq)
                elif mtype in ("video", "animated_gif"):
                    has_video = True
                    if hq not in image_urls:
                        image_urls.append(hq)  # thumbnail
                    # Extract actual video MP4 URL (highest bitrate)
                    variants = (m.get("video_info", {}) or {}).get("variants", []) or []
                    mp4s = [v for v in variants if v.get("content_type") == "video/mp4"]
                    if mp4s:
                        best = max(mp4s, key=lambda v: v.get("bitrate", 0) or 0)
                        v_url = best.get("url")
                        if v_url and v_url not in video_urls:
                            video_urls.append(v_url)

        # 1) Media from the post itself
        ext_media = (legacy.get("extended_entities", {}) or {}).get("media") or media_list
        _collect_media(ext_media)

        # 2) Media from a QUOTED tweet (if this is a quote-tweet)
        quoted = tweet_result.get("quoted_status_result", {}) or {}
        quoted_caption = ""
        quoted_author = ""
        if quoted:
            q_result = quoted.get("result", {})
            if q_result.get("__typename") == "TweetWithVisibilityResults":
                q_result = q_result.get("tweet", {})
            q_legacy = q_result.get("legacy", {}) or {}
            if q_legacy:
                # quoted author
                q_core = q_result.get("core", {})
                q_user = (q_core.get("user_results", {}) or {}).get("result", {})
                quoted_author = (q_user.get("core", {}).get("screen_name")
                                 or q_user.get("legacy", {}).get("screen_name", ""))

                # quoted text
                q_note = (q_result.get("note_tweet", {})
                          .get("note_tweet_results", {})
                          .get("result", {}))
                if q_note and q_note.get("text"):
                    quoted_caption = q_note["text"]
                else:
                    quoted_caption = q_legacy.get("full_text", "") or ""
                quoted_caption = html.unescape(quoted_caption.strip())

                # quoted media
                q_ext_media = (
                    (q_legacy.get("extended_entities", {}) or {}).get("media")
                    or q_legacy.get("entities", {}).get("media", [])
                )
                _collect_media(q_ext_media)

        # 3) Media from the retweeted_status (for true retweets)
        if is_retweet:
            rt_result = (legacy.get("retweeted_status_result", {}) or {}).get("result", {})
            if rt_result.get("__typename") == "TweetWithVisibilityResults":
                rt_result = rt_result.get("tweet", {})
            rt_legacy = rt_result.get("legacy", {}) or {}
            if rt_legacy:
                # Use retweet's full text/media
                rt_core = rt_result.get("core", {})
                rt_user = (rt_core.get("user_results", {}) or {}).get("result", {})
                original_author = (rt_user.get("core", {}).get("screen_name")
                                   or rt_user.get("legacy", {}).get("screen_name", ""))
                rt_note = (rt_result.get("note_tweet", {})
                           .get("note_tweet_results", {})
                           .get("result", {}))
                if rt_note and rt_note.get("text"):
                    caption = rt_note["text"]
                elif rt_legacy.get("full_text"):
                    caption = rt_legacy["full_text"]
                caption = html.unescape(caption.strip())
                quoted_author = original_author  # store original author here

                rt_ext_media = (
                    (rt_legacy.get("extended_entities", {}) or {}).get("media")
                    or rt_legacy.get("entities", {}).get("media", [])
                )
                _collect_media(rt_ext_media)

        # Determine post type: video > retweet > quote > normal
        if has_video:
            post_type = "video"
        elif is_retweet:
            post_type = "retweet"
        elif is_quote:
            post_type = "quote"
        else:
            post_type = "post"

        # ── Engagement counts ─────────────────────────────────────────
        # For RETWEETS we must read the ORIGINAL tweet's counts, not the
        # retweet wrapper's. The retweet wrapper has favorite_count=0,
        # retweet_count=0, reply_count=0 — but X displays the original
        # tweet's numbers in the user's timeline. Using wrapper counts
        # produces wildly wrong values (often 0 or single digits) for
        # retweeted popular posts.
        engagement_legacy = legacy
        engagement_views_obj = tweet_result.get("views", {}) or {}
        if is_retweet:
            rt_result = ((legacy.get("retweeted_status_result") or {}).get("result") or {})
            if rt_result.get("__typename") == "TweetWithVisibilityResults":
                rt_result = rt_result.get("tweet", {}) or {}
            rt_legacy = rt_result.get("legacy") or {}
            if rt_legacy:
                engagement_legacy = rt_legacy
                # Original tweet's views are on rt_result, not its legacy
                rt_views = rt_result.get("views", {}) or {}
                if rt_views.get("count") is not None:
                    engagement_views_obj = rt_views

        likes    = int(engagement_legacy.get("favorite_count", 0) or 0)
        retweets = int(engagement_legacy.get("retweet_count", 0) or 0)
        comments = int(engagement_legacy.get("reply_count", 0) or 0)

        views = 0
        v_count = engagement_views_obj.get("count")
        if v_count is not None:
            try:
                views = int(v_count)
            except (ValueError, TypeError):
                pass

        # Original tweet ID (for retweets) — used by the syndication CDN
        # enrichment, since the retweet ID itself isn't in the CDN.
        original_tweet_id = tweet_id
        if is_retweet:
            rt_result = ((legacy.get("retweeted_status_result") or {}).get("result") or {})
            if rt_result.get("__typename") == "TweetWithVisibilityResults":
                rt_result = rt_result.get("tweet", {}) or {}
            rt_legacy = rt_result.get("legacy") or {}
            orig_id = rt_legacy.get("id_str") or rt_result.get("rest_id")
            if orig_id:
                original_tweet_id = orig_id

        dt = parse_twitter_date(legacy.get("created_at", ""))
        created_at_iso = dt.isoformat() if dt else ""

        return {
            "username": username,
            "post_url": f"https://x.com/{username}/status/{tweet_id}",
            "caption": caption,
            "likes": likes,
            "retweets": retweets,
            "comments": comments,
            "views": views,
            "image_urls": image_urls,
            "video_urls": video_urls,
            "post_type": post_type,         # "post" | "retweet" | "quote" | "video"
            "is_retweet": is_retweet,
            "is_quote": is_quote,
            "has_video": has_video,
            "quoted_author": quoted_author,
            "quoted_caption": quoted_caption,
            "_original_tweet_id": original_tweet_id,  # for CDN enrichment
            "created_at": created_at_iso,
            "_dt": dt,
        }
    except Exception as e:
        print(f"[WARN] extract_tweet_data: {e}")
        return None


def walk_instructions(instructions, username, posts_dict):
    for instr in instructions or []:
        itype = instr.get("type", "")
        if itype == "TimelinePinEntry":
            continue
        if itype == "TimelineAddEntries":
            entries = instr.get("entries", []) or []
        elif itype == "TimelineAddToModule":
            entries = instr.get("moduleItems", []) or []
        else:
            continue

        for entry in entries:
            content = entry.get("content") or entry.get("item", {}).get("content", {})
            if not content:
                continue

            item_content = content.get("itemContent", {})
            if item_content.get("itemType") == "TimelineTweet":
                data = extract_tweet_data(item_content.get("tweet_results", {}), username)
                if data:
                    tid = data["post_url"].split("/")[-1]
                    posts_dict.setdefault(tid, data)

            if content.get("entryType") == "TimelineTimelineModule":
                for item in content.get("items", []) or []:
                    inner = item.get("item", {}).get("itemContent", {})
                    if inner.get("itemType") == "TimelineTweet":
                        data = extract_tweet_data(inner.get("tweet_results", {}), username)
                        if data:
                            tid = data["post_url"].split("/")[-1]
                            posts_dict.setdefault(tid, data)


# =============================================================
# PUBLIC API
# =============================================================

def _matches(dt, threshold, range_start, range_end):
    if dt is None:
        if threshold or range_start or range_end:
            return False
        return True
    if threshold and dt < threshold:
        return False
    if range_start and dt < range_start:
        return False
    if range_end and dt > range_end:
        return False
    return True


def _fetch_all_posts_for_user(username, max_pages=35, target_count=None):
    global _RATE_LIMIT_UNTIL
    key = username.lower()
    now_ts = time.time()

    entry = _TWEETS_CACHE.get(key)
    if entry:
        ts, posts = entry
        if posts and (now_ts - ts < _TWEETS_CACHE_TTL):
            return posts, None

    if now_ts < _RATE_LIMIT_UNTIL and entry:
        ts, posts = entry
        if posts and (now_ts - ts < _TWEETS_CACHE_STALE_TTL):
            return posts, None

    # Try personal cookies first, then fall back to guest token
    posts_dict = {}
    fetch_error = None

    for session_mode in ("cookies", "guest"):
        try:
            session = build_session(use_guest=(session_mode == "guest"))
        except Exception as e:
            fetch_error = f"session: {e}"
            continue

        user_id, err = get_user_id(session, username)
        if err in ("suspended", "not_found", "protected"):
            return None, err

        if err:
            fetch_error = err
            # If 401/403/429 and we still have a fallback to try, continue
            if session_mode == "cookies" and ("401" in str(err) or "403" in str(err) or "429" in str(err)):
                print(f"[Fallback] Cookies failed ({err}), trying guest token...")
                continue
            if entry and entry[1]:
                return entry[1], None
            return [], err

        # Got user_id - fetch tweets
        cursor = None
        success_pages = 0
        for page_num in range(max_pages):
            instructions, next_cursor, page_err = fetch_tweets_page(
                session, user_id, cursor=cursor, count=60
            )
            if page_err:
                fetch_error = page_err
                break
            success_pages += 1
            walk_instructions(instructions, username, posts_dict)
            # Stop early if we already have enough posts (target_count + 20% buffer for filtering)
            if target_count and len(posts_dict) >= int(target_count * 1.2):
                break
            if not next_cursor:
                break
            cursor = next_cursor

        # If we got at least one page successfully, stop trying fallbacks
        if success_pages > 0:
            fetch_error = None
            break

        # If error on cookies → try guest
        if session_mode == "cookies" and fetch_error:
            print(f"[Fallback] Tweets fetch failed ({fetch_error}), trying guest token...")
            continue
        break

    posts_list = list(posts_dict.values())
    posts_list.sort(
        key=lambda p: p.get("_dt") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )

    if posts_list:
        _TWEETS_CACHE[key] = (time.time(), posts_list)
        return posts_list, None

    if entry and entry[1]:
        return entry[1], None

    return [], fetch_error


# =============================================================
# SEARCH POSTS (by keyword or hashtag)
# =============================================================

def _extract_tweet_for_search(tweet_result):
    """Like extract_tweet_data but author-agnostic (returns any tweet)."""
    try:
        if "result" in tweet_result:
            tweet_result = tweet_result["result"]
        if tweet_result.get("__typename") == "TweetWithVisibilityResults":
            tweet_result = tweet_result.get("tweet", {})

        legacy = tweet_result.get("legacy", {})
        if not legacy:
            return None

        # Skip replies
        if legacy.get("in_reply_to_status_id_str") or legacy.get("in_reply_to_user_id_str"):
            return None

        is_retweet = bool(legacy.get("retweeted_status_result") or legacy.get("retweeted_status_id_str"))
        is_quote   = bool(legacy.get("is_quote_status") or tweet_result.get("quoted_status_result"))

        tweet_id = legacy.get("id_str", "")
        if not tweet_id:
            return None

        # Author
        core = tweet_result.get("core", {})
        user_result = (core.get("user_results", {}) or {}).get("result", {})
        user_legacy = user_result.get("legacy", {})
        author = (user_result.get("core", {}).get("screen_name")
                  or user_legacy.get("screen_name", "")
                  or "user")

        # Caption (note_tweet for long, else full_text)
        note_tweet = (tweet_result.get("note_tweet", {})
                      .get("note_tweet_results", {})
                      .get("result", {}))
        caption = note_tweet.get("text") if note_tweet else None
        if not caption:
            caption = legacy.get("full_text", "") or ""

        entities = legacy.get("entities", {})
        for ue in entities.get("urls", []) or []:
            short = ue.get("url", "")
            expanded = ue.get("expanded_url", "")
            if short and expanded:
                caption = caption.replace(short, expanded)
        media_list = entities.get("media", []) or []
        for m in media_list:
            short = m.get("url", "")
            if short and short in caption:
                caption = caption.replace(short, "")
        caption = html.unescape(caption.strip())

        # Images / videos
        image_urls = []
        video_urls = []
        has_video = False
        ext_media = (legacy.get("extended_entities", {}) or {}).get("media") or media_list
        for m in ext_media:
            mtype = m.get("type")
            url = m.get("media_url_https", "")
            if not url:
                continue
            base = url.split("?")[0]
            hq = f"{base}?format=jpg&name=large"
            if mtype == "photo":
                if hq not in image_urls:
                    image_urls.append(hq)
            elif mtype in ("video", "animated_gif"):
                has_video = True
                if hq not in image_urls:
                    image_urls.append(hq)
                variants = (m.get("video_info", {}) or {}).get("variants", []) or []
                mp4s = [v for v in variants if v.get("content_type") == "video/mp4"]
                if mp4s:
                    best = max(mp4s, key=lambda v: v.get("bitrate", 0) or 0)
                    v_url = best.get("url")
                    if v_url and v_url not in video_urls:
                        video_urls.append(v_url)

        likes    = int(legacy.get("favorite_count", 0) or 0)
        retweets = int(legacy.get("retweet_count", 0) or 0)
        comments = int(legacy.get("reply_count", 0) or 0)
        views = 0
        v_obj = tweet_result.get("views", {}) or {}
        v_count = v_obj.get("count")
        if v_count is not None:
            try:
                views = int(v_count)
            except (ValueError, TypeError):
                pass

        dt = parse_twitter_date(legacy.get("created_at", ""))
        created_at_iso = dt.isoformat() if dt else ""

        post_type = "video" if has_video else "retweet" if is_retweet else "quote" if is_quote else "post"

        return {
            "username": author,
            "post_url": f"https://x.com/{author}/status/{tweet_id}",
            "caption": caption,
            "likes": likes, "retweets": retweets, "comments": comments, "views": views,
            "image_urls": image_urls, "video_urls": video_urls,
            "post_type": post_type,
            "is_retweet": is_retweet, "is_quote": is_quote, "has_video": has_video,
            "quoted_author": "", "quoted_caption": "",
            "created_at": created_at_iso,
            "_dt": dt,
        }
    except Exception as e:
        print(f"[WARN] _extract_tweet_for_search: {e}")
        return None


def _walk_search_instructions(instructions, posts_dict):
    """Walk search-timeline instructions and collect tweets."""
    for instr in (instructions or []):
        itype = instr.get("type", "")
        if itype != "TimelineAddEntries":
            continue
        for entry in instr.get("entries", []) or []:
            content = entry.get("content", {})
            ic = content.get("itemContent", {})
            if ic.get("itemType") == "TimelineTweet":
                data = _extract_tweet_for_search(ic.get("tweet_results", {}))
                if data:
                    tid = data["post_url"].split("/")[-1]
                    posts_dict.setdefault(tid, data)
            # Conversation modules
            if content.get("entryType") == "TimelineTimelineModule":
                for item in content.get("items", []) or []:
                    inner = item.get("item", {}).get("itemContent", {})
                    if inner.get("itemType") == "TimelineTweet":
                        data = _extract_tweet_for_search(inner.get("tweet_results", {}))
                        if data:
                            tid = data["post_url"].split("/")[-1]
                            posts_dict.setdefault(tid, data)


# =============================================================
# PERSISTENT SELENIUM DRIVER (singleton — reused across requests)
# Saves 5-10s startup per request.
# =============================================================
_DRIVER = None
_DRIVER_LOCK = threading.Lock()
_DRIVER_READY = False  # True once cookies are injected


def _build_selenium_driver():
    """Create a fresh headless Chrome driver tuned for speed."""
    import os
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--log-level=3")
    opts.add_argument("--window-size=1280,1600")
    # Note: We force English UI via a `lang=en` cookie injected after navigation,
    # not via Chrome flags — `--accept-lang` and `--lang` can interfere with X.
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.page_load_strategy = "eager"
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

    # Use system-installed Chrome/Chromium if available (Docker/Render)
    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin:
        opts.binary_location = chrome_bin

    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
    if chromedriver_path:
        driver = webdriver.Chrome(service=Service(chromedriver_path), options=opts)
    else:
        driver = webdriver.Chrome(options=opts)

    driver.set_page_load_timeout(25)
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        })
    except Exception:
        pass
    return driver


def _get_driver():
    """Return the singleton driver, creating + warming it up once."""
    global _DRIVER, _DRIVER_READY
    with _DRIVER_LOCK:
        # Detect a dead driver and recreate
        if _DRIVER is not None:
            try:
                _ = _DRIVER.title  # cheap roundtrip
            except Exception:
                try: _DRIVER.quit()
                except Exception: pass
                _DRIVER = None
                _DRIVER_READY = False

        if _DRIVER is None:
            _DRIVER = _build_selenium_driver()
            _DRIVER_READY = False

        if not _DRIVER_READY:
            # One-time cookie injection (warm-up).
            # Note: X (2024+) REQUIRES login even for /search — guest mode does not work.
            # If your account has "Translate posts" enabled, X replaces the tweet text
            # with the translation in the DOM. Disable it from:
            #   x.com Settings → Accessibility, display and languages → Languages
            #   → Uncheck "Translate posts"
            try:
                _DRIVER.get("https://x.com")
                time.sleep(1.5)
                try:
                    _DRIVER.delete_all_cookies()
                except Exception:
                    pass
                _DRIVER.add_cookie({"name": "auth_token", "value": AUTH_TOKEN, "domain": ".x.com", "path": "/"})
                _DRIVER.add_cookie({"name": "ct0",        "value": CT0,        "domain": ".x.com", "path": "/"})
                _DRIVER_READY = True
            except Exception as e:
                print(f"[Driver warmup] {e}")
        return _DRIVER


def _shutdown_driver():
    """Optional clean-up (e.g. on FastAPI shutdown)."""
    global _DRIVER, _DRIVER_READY
    with _DRIVER_LOCK:
        if _DRIVER:
            try: _DRIVER.quit()
            except Exception: pass
            _DRIVER = None
            _DRIVER_READY = False
    # Also shut down the pool
    with _POOL_LOCK:
        while _DRIVER_POOL:
            drv = _DRIVER_POOL.pop()
            try: drv.quit()
            except Exception: pass


# =============================================================
# DRIVER POOL — for parallel chunked searches
# =============================================================
_DRIVER_POOL = []          # idle drivers available for checkout
_POOL_LOCK = threading.Lock()
_POOL_MAX = 3              # max concurrent drivers (each = 1 Chrome process)


def _build_warmed_driver():
    """Create a driver and inject auth cookies (ready to search)."""
    d = _build_selenium_driver()
    try:
        d.get("https://x.com")
        time.sleep(1.2)
        try: d.delete_all_cookies()
        except Exception: pass
        d.add_cookie({"name": "auth_token", "value": AUTH_TOKEN, "domain": ".x.com", "path": "/"})
        d.add_cookie({"name": "ct0",        "value": CT0,        "domain": ".x.com", "path": "/"})
    except Exception as e:
        print(f"[Pool driver warmup] {e}")
    return d


def _checkout_driver():
    """Get a driver from the pool, creating one if none idle and below cap."""
    with _POOL_LOCK:
        if _DRIVER_POOL:
            return _DRIVER_POOL.pop()
    # Build outside the lock — Chrome startup is slow
    return _build_warmed_driver()


def _return_driver(d):
    """Return a driver to the pool, capped at _POOL_MAX."""
    if d is None:
        return
    # Verify the driver is alive
    try:
        _ = d.title
    except Exception:
        try: d.quit()
        except Exception: pass
        return
    with _POOL_LOCK:
        if len(_DRIVER_POOL) < _POOL_MAX:
            _DRIVER_POOL.append(d)
            return
    try: d.quit()
    except Exception: pass


# =============================================================
# SYNDICATION CDN - returns ORIGINAL tweet text (no translation)
# This bypasses X's account-level auto-translate setting.
# =============================================================

# Shared session for syndication calls (keep-alive for speed)
_SYND_SESSION = requests.Session()
_SYND_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
})


def _make_syndication_token(tweet_id):
    """Generate the obscure token X requires for syndication API calls."""
    try:
        n = int(tweet_id) / 1e15 * math.pi
        return format(n, "f").replace(".", "").rstrip("0")[:11]
    except Exception:
        return ""


def _safe_int(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _hq_image(url):
    """Upgrade any pbs.twimg.com image URL to large/original quality."""
    if not url:
        return url
    base = url.split("?")[0]
    # Strip any existing &name=... query
    return f"{base}?format=jpg&name=large"


def _extract_media_from_cdn(d):
    """
    Pull ALL image + video URLs from a syndication-CDN response.
    Looks at every known media field — covers single photos, 2-4 photo
    grids, videos, animated GIFs, AND media inside a quoted tweet.

    Returns (image_urls, video_urls, has_video).
    """
    image_urls = []
    video_urls = []
    has_video = False
    seen_imgs = set()
    seen_vids = set()

    def _push_img(u):
        u = _hq_image(u)
        if u and u not in seen_imgs:
            seen_imgs.add(u)
            image_urls.append(u)

    def _push_vid(u):
        if u and u not in seen_vids:
            seen_vids.add(u)
            video_urls.append(u)

    def _process_media_array(arr):
        nonlocal has_video
        for m in (arr or []):
            if not isinstance(m, dict):
                continue
            mtype = (m.get("type") or "").lower()
            # 1) photo thumbnail / preview (every media item has this)
            img_url = (m.get("media_url_https")
                       or m.get("media_url")
                       or m.get("url"))
            if img_url:
                _push_img(img_url)
            # 2) video / animated-gif: pick highest-bitrate mp4 variant
            if mtype in ("video", "animated_gif"):
                has_video = True
                variants = ((m.get("video_info") or {}).get("variants")
                            or m.get("variants") or [])
                mp4s = [v for v in variants
                        if (v.get("content_type") or v.get("type") or "") == "video/mp4"]
                if mp4s:
                    best = max(mp4s, key=lambda v: v.get("bitrate", 0) or 0)
                    _push_vid(best.get("url") or best.get("src"))

    # ── Primary media payload ───────────────────────────────
    _process_media_array(d.get("mediaDetails"))

    # ── Fallback `photos` array (older schema) ──────────────
    for p in (d.get("photos") or []):
        if isinstance(p, dict):
            _push_img(p.get("url"))

    # ── Top-level video object (some embedded tweets) ───────
    v = d.get("video")
    if isinstance(v, dict):
        has_video = True
        _push_img(v.get("poster"))
        for vr in (v.get("variants") or []):
            if (vr.get("type") or vr.get("content_type") or "") == "video/mp4":
                _push_vid(vr.get("src") or vr.get("url"))

    # ── Quoted tweet media ──────────────────────────────────
    q = d.get("quoted_tweet") or d.get("quotedStatus") or {}
    if isinstance(q, dict) and q:
        _process_media_array(q.get("mediaDetails"))
        for p in (q.get("photos") or []):
            if isinstance(p, dict):
                _push_img(p.get("url"))

    return image_urls, video_urls, has_video


def _fetch_original_tweet(tweet_id):
    """
    Fetch a single tweet from X's syndication CDN. Returns:
        text, lang, screen_name, created_at,
        likes (favorite_count — EXACT integer),
        replies (conversation_count — EXACT integer),
        retweets (retweet_count if present, else 0),
        views (multiple possible keys),
        image_urls, video_urls, has_video.

    The CDN returns EXACT counts — not the rounded "1.9K" you see on x.com.
    """
    if not tweet_id:
        return None
    token = _make_syndication_token(tweet_id)
    url = (
        f"https://cdn.syndication.twimg.com/tweet-result"
        f"?id={tweet_id}&token={token}&lang=en"
    )
    # Retry once on transient 404 (CDN edge cache warm-up on fresh tweets)
    d = None
    for attempt in range(2):
        try:
            r = _SYND_SESSION.get(url, timeout=8)
            if r.status_code == 200:
                d = r.json()
                break
            if r.status_code == 404 and attempt == 0:
                time.sleep(0.6)
                continue
            return None
        except Exception:
            if attempt == 0:
                time.sleep(0.4)
                continue
            return None
    if d is None or not isinstance(d, dict):
        return None
    try:
        # ── Views: try every known key X has used over the years ──
        views = 0
        for k in ("view_count", "views_count", "ext_view_count"):
            v = d.get(k)
            if v:
                views = _safe_int(v)
                break
        if not views:
            v_obj = d.get("views") or d.get("ext_views")
            if isinstance(v_obj, dict):
                views = _safe_int(v_obj.get("count") or v_obj.get("state"))
            elif v_obj:
                views = _safe_int(v_obj)

        image_urls, video_urls, has_video = _extract_media_from_cdn(d)

        return {
            "text":        d.get("text") or "",
            "lang":        d.get("lang") or "",
            "screen_name": (d.get("user") or {}).get("screen_name") or "",
            "created_at":  d.get("created_at") or "",
            "likes":       _safe_int(d.get("favorite_count")),
            "replies":     _safe_int(d.get("conversation_count")),
            "retweets":    _safe_int(d.get("retweet_count")),
            "views":       _safe_int(views),
            "image_urls":  image_urls,
            "video_urls":  video_urls,
            "has_video":   has_video,
        }
    except Exception as e:
        print(f"[CDN parse] {tweet_id}: {e}")
        return None


# =============================================================
# LIVE COUNT REFRESH via GraphQL TweetResultByRestId
# =============================================================
# The syndication CDN ages ~30-300s. For "live" matching what X.com
# shows at this moment, we hit the authenticated GraphQL endpoint
# which returns fresh counts for each tweet ID.

_LIVE_SESSION = None
_LIVE_SESSION_LOCK = threading.Lock()


def _get_live_session():
    """Build (once) an authenticated session for the GraphQL refresh path."""
    global _LIVE_SESSION
    with _LIVE_SESSION_LOCK:
        if _LIVE_SESSION is None:
            _LIVE_SESSION = build_session(use_guest=False)
    return _LIVE_SESSION


_LIVE_FEATURES = {
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "premium_content_api_read_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
    "responsive_web_grok_analyze_post_followups_enabled": False,
    "responsive_web_jetfuel_frame": False,
    "responsive_web_grok_share_attachment_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
}


def _fetch_tweet_live(tweet_id):
    """
    Live engagement counts for a single tweet via the authenticated
    GraphQL TweetResultByRestId endpoint. Returns
        {likes, retweets, comments, views}
    or None on any error. Bypasses the syndication-CDN edge cache.
    """
    if not tweet_id:
        return None
    session = _get_live_session()
    variables = {
        "tweetId": str(tweet_id),
        "withCommunity": False,
        "includePromotedContent": False,
        "withVoice": False,
    }
    url = f"{GRAPHQL_BASE}/{TWEET_BY_REST_ID}/TweetResultByRestId"
    params = {
        "variables": json.dumps(variables, separators=(",", ":")),
        "features":  json.dumps(_LIVE_FEATURES, separators=(",", ":")),
    }
    try:
        r = session.get(url, params=params, timeout=8)
        if r.status_code != 200:
            return None
        data = r.json()
        tw = (data.get("data") or {}).get("tweetResult", {}).get("result", {})
        if not tw:
            return None
        if tw.get("__typename") == "TweetWithVisibilityResults":
            tw = tw.get("tweet", {})
        legacy = tw.get("legacy") or {}
        if not legacy:
            return None
        views = tw.get("views") or {}
        return {
            "likes":    _safe_int(legacy.get("favorite_count")),
            "retweets": _safe_int(legacy.get("retweet_count")),
            "comments": _safe_int(legacy.get("reply_count")),
            "views":    _safe_int(views.get("count")),
        }
    except Exception:
        return None


def _enrich_with_originals(posts, max_workers=10):
    """
    For every post: fetch authoritative data from X's syndication CDN and
    merge into the existing post dict.

    Merge rules
    ─ Caption: replace with CDN text if non-empty (bypasses auto-translate).
    ─ Counts : take MAX(DOM, CDN). DOM may be rounded ("1.9K" → 1900);
              CDN gives EXACT ("1923"). Whichever is higher is the truth.
              When DOM is 0 (fresh tweet, counters not rendered) and CDN
              has the real number, this picks the CDN value.
    ─ Media  : UNION (CDN images + DOM images, deduped). The CDN is the
              authoritative source for media — it lists every image and
              video URL even if X collapsed some in the feed view.
    """
    if not posts:
        return posts

    def _enrich(post):
        # For retweets the CDN doesn't index the retweet wrapper — fetch the
        # ORIGINAL tweet (we stashed its id during extraction).
        tid = (
            post.get("_original_tweet_id")
            or (post.get("post_url") or "").split("/")[-1]
        )
        if not tid:
            return

        # ── Hit BOTH sources in this thread:
        #    1. Syndication CDN — gives original text + media metadata
        #    2. GraphQL TweetResultByRestId — gives LIVE engagement counts
        #       (the X account-authenticated GraphQL is not edge-cached)
        orig = _fetch_original_tweet(tid)
        live = _fetch_tweet_live(tid)

        if not orig and not live:
            return

        # 1) Caption — replace with original text from CDN (bypass auto-translate)
        if orig and orig["text"]:
            post["caption"] = orig["text"]

        # 2) Counts — take the MAXIMUM across DOM, CDN, and LIVE GraphQL.
        #    LIVE GraphQL is fresh; DOM may be rounded; CDN may be stale.
        #    Max never goes backwards from what we already had.
        def _max3(dom_v, cdn_v, live_v):
            return max(_safe_int(dom_v), _safe_int(cdn_v), _safe_int(live_v))

        post["likes"] = _max3(
            post.get("likes"),
            (orig or {}).get("likes", 0),
            (live or {}).get("likes", 0),
        )
        post["comments"] = _max3(
            post.get("comments"),
            (orig or {}).get("replies", 0),
            (live or {}).get("comments", 0),
        )
        post["retweets"] = _max3(
            post.get("retweets"),
            (orig or {}).get("retweets", 0),
            (live or {}).get("retweets", 0),
        )
        post["views"] = _max3(
            post.get("views"),
            (orig or {}).get("views", 0),
            (live or {}).get("views", 0),
        )

        # 3) Media — UNION of DOM images + CDN images (CDN is authoritative
        # for completeness; DOM may have caught images the CDN missed).
        if orig:
            existing_imgs = list(post.get("image_urls") or [])
            existing_vids = list(post.get("video_urls") or [])
            seen_v = set(existing_vids)
            norm_imgs = []
            for u in existing_imgs:
                hq = _hq_image(u)
                if hq not in [_hq_image(x) for x in norm_imgs]:
                    norm_imgs.append(hq)
            for u in orig["image_urls"]:
                if u not in [_hq_image(x) for x in norm_imgs]:
                    norm_imgs.append(u)
            post["image_urls"] = norm_imgs
            for v in orig["video_urls"]:
                if v not in seen_v:
                    existing_vids.append(v)
                    seen_v.add(v)
            post["video_urls"] = existing_vids
            if orig["has_video"]:
                post["has_video"] = True
                if post.get("post_type") == "post":
                    post["post_type"] = "video"

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(_enrich, posts))
    return posts


def _selenium_search(query, limit=10, mode="keyword",
                     since_date=None, until_date=None,
                     driver=None):
    """
    Use Selenium to scrape x.com/search?q=... (Latest tab).
    If `driver` is provided we use it (caller owns the lifecycle); otherwise
    we use the singleton from `_get_driver()`.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException

    if mode == "hashtag":
        q = query.lstrip("#")
        search_q = f"#{q}"
    else:
        search_q = query

    extras = []
    if since_date:
        extras.append(f"since:{since_date}")
    if until_date:
        extras.append(f"until:{until_date}")
    if extras:
        search_q = f"{search_q} {' '.join(extras)}"

    encoded = quote(search_q)
    url = f"https://x.com/search?q={encoded}&src=typed_query&f=live"
    print(f"[Selenium search] URL: {url}")

    if driver is None:
        driver = _get_driver()

    # Open the search results page (cookies were injected once in _get_driver)
    try:
        driver.get(url)
    except Exception as e:
        print(f"[Selenium search] navigation error: {e}")
        return []

    try:
        WebDriverWait(driver, 18).until(
            EC.presence_of_element_located((By.TAG_NAME, "article"))
        )
        # Settle so the engagement counters finish their 0→target animation.
        # X uses an animated transition span; reading mid-animation returns
        # a partial value (e.g. 794 on a tweet that ultimately shows 1626).
        # 1.6s reliably catches the final value for all counts < 1M.
        time.sleep(1.6)
    except TimeoutException:
        page_src = driver.page_source.lower()
        if "no results for" in page_src or "لا توجد نتائج" in page_src:
            print("[Selenium search] X says: no results")
        elif "rate limit" in page_src or "تم تجاوز" in page_src:
            print("[Selenium search] X says: rate limit hit — backing off 30s")
            time.sleep(30)
        elif ("are you a robot" in page_src or "verify you are human" in page_src
              or "unusual activity" in page_src or "automated" in page_src):
            print("[Selenium search] X is showing anti-bot verify page — backing off 30s")
            time.sleep(30)
        elif "log in" in page_src or "sign in" in page_src or "sign up" in page_src:
            print("[Selenium search] X requires login (cookies might be invalid)")
        else:
            try:
                title = driver.title
                print(f"[Selenium search] No articles found. Page title: {title!r}")
            except Exception:
                pass
        return []

    # ─── FAST EXTRACTION VIA JAVASCRIPT ──────────────────────────────
    # Pulling each <article> via Selenium WebElement calls is ~10× slower
    # than running one JS query that returns a JSON blob.
    EXTRACT_JS = r"""
    const articles = document.querySelectorAll('article');
    const results = [];

    // Normalize Arabic-Indic and Persian digits to ASCII 0-9.
    function asciiDigits(s) {
        if (!s) return '';
        return String(s)
            .replace(/[٠-٩]/g, d => String(d.charCodeAt(0) - 0x0660))
            .replace(/[۰-۹]/g, d => String(d.charCodeAt(0) - 0x06F0));
    }

    function numFromStr(str) {
        if (!str) return 0;
        const s0 = asciiDigits(str);
        const m = s0.match(/([\d.,]+\s*[KMB]?)/i);
        if (!m) return 0;
        let s = m[1].replace(/[,\s]/g, '');
        let mult = 1;
        if (/k$/i.test(s)) { mult = 1000;       s = s.slice(0, -1); }
        else if (/m$/i.test(s)) { mult = 1000000; s = s.slice(0, -1); }
        else if (/b$/i.test(s)) { mult = 1000000000; s = s.slice(0, -1); }
        const n = parseFloat(s);
        return isNaN(n) ? 0 : Math.round(n * mult);
    }

    // Read the EXACT count from aria-label. X always renders the full count
    // there (e.g. "1,626 Views. View" / "13 Likes. Like" / "0 Replies. Reply")
    // — even before any visible counter animation finishes. Walking inner
    // spans/text is unreliable because relative timestamps ("3m", "2h") in
    // the same DOM scope get mis-parsed as counts.
    function ariaCount(el) {
        if (!el) return 0;
        return numFromStr(el.getAttribute('aria-label') || '');
    }

    function readButtonCount(btn) { return ariaCount(btn); }

    function readViewCount(art) {
        const grp = art.querySelector('[role="group"]') || art;
        let best = 0;

        // 1) Action-group aria-label is the most reliable single string
        //    e.g. "6 reposts, 8 likes, 5 bookmarks, 181 views"
        const grpAria = asciiDigits(grp.getAttribute('aria-label') || '').toLowerCase();
        if (grpAria) {
            const m = grpAria.match(/([\d,.]+\s*[kmb]?)\s*(?:view|مشاهد)/i);
            if (m) best = Math.max(best, numFromStr(m[1]));
        }

        // 2) The analytics anchor — usually no aria-label, but its
        //    textContent is "163 Views" / "1.6K Views" / "١٦٣ مشاهد..."
        const linkCandidates = [
            grp.querySelector('a[href$="/analytics"]'),
            grp.querySelector('a[role="link"][href*="/analytics"]'),
            grp.querySelector('[data-testid="analyticsLink"]'),
        ].filter(Boolean);
        for (const el of linkCandidates) {
            best = Math.max(best, numFromStr(el.getAttribute('aria-label') || ''));
            best = Math.max(best, numFromStr((el.textContent || '').trim()));
        }

        return best;
    }

    // Extract ORIGINAL caption text — skip any "Show translation" button or translated content
    function getOriginalCaption(art) {
        // X renders the translated text in a separate block with data-testid="tweetText"
        // The ORIGINAL is always in the FIRST tweetText element of the article
        const all = art.querySelectorAll('[data-testid="tweetText"]');
        if (all.length === 0) return '';
        // Pick the first one (original is rendered first; translation appears below)
        let txt = '';
        all[0].childNodes.forEach(node => {
            // Skip the "Show translation" / "Translate post" button if present inside
            if (node.nodeType === 1) {
                const t = (node.innerText || node.textContent || '');
                if (/show translation|translate this post|اعرض الترجمة|عرض الترجمة|ترجم/i.test(t)) return;
            }
            txt += (node.textContent || '');
        });
        return txt || (all[0].innerText || '');
    }

    for (const art of articles) {
        const timeEl = art.querySelector('time');
        if (!timeEl) continue;
        const linkEl = timeEl.closest('a');
        if (!linkEl) continue;
        const href = linkEl.getAttribute('href') || '';
        const m = href.match(/\/([^/]+)\/status\/(\d+)/);
        if (!m) continue;

        // Capture EVERY image in the tweet — including multi-photo grids,
        // link-preview card thumbnails, and images inside a quoted tweet.
        const images = [];
        const seen = new Set();
        const imgSelectors = [
            '[data-testid="tweetPhoto"] img',          // normal photos (1-4 grid)
            '[data-testid="card.wrapper"] img',         // link-preview cards
            '[data-testid="card.layoutLarge.media"] img',
            '[data-testid="card.layoutSmall.media"] img',
            'a[href*="/photo/"] img',                   // any clickable photo
            'div[aria-label="Image"] img',
            'img[src*="pbs.twimg.com/media"]',          // catch-all by URL
        ];
        imgSelectors.forEach(sel => {
            art.querySelectorAll(sel).forEach(img => {
                const s = img.getAttribute('src') || '';
                if (!s) return;
                if (s.includes('profile_images')) return;   // skip avatars
                if (s.includes('emoji')) return;            // skip emoji glyphs
                if (s.includes('semantic_core_img')) return;// skip ad/feature icons
                if (seen.has(s)) return;
                seen.add(s);
                images.push(s);
            });
        });

        // Counts: scope to the action `role="group"` so we read the OUTER
        // tweet's buttons, never a quoted-tweet's buttons.
        const actionGroup = art.querySelector('[role="group"]') || art;
        const replyBtn   = actionGroup.querySelector('[data-testid="reply"]');
        const retweetBtn = actionGroup.querySelector('[data-testid="retweet"]')
                       || actionGroup.querySelector('[data-testid="unretweet"]');
        const likeBtn    = actionGroup.querySelector('[data-testid="like"]')
                       || actionGroup.querySelector('[data-testid="unlike"]');

        let comments = readButtonCount(replyBtn);
        let retweets = readButtonCount(retweetBtn);
        let likes    = readButtonCount(likeBtn);
        let views    = readViewCount(art);

        // Also parse the action group's combined aria-label as a SECONDARY
        // truth source. It looks like "2 replies, 3 reposts, 8 likes, 1626 views".
        // We take the MAX of (individual button reading, group aria value).
        const groupEl = art.querySelector('[role="group"][aria-label]');
        const groupAria = groupEl ? (groupEl.getAttribute('aria-label') || '') : '';
        if (groupAria) {
            asciiDigits(groupAria).split(/[,،]/).forEach(part => {
                const p = part.trim().toLowerCase();
                const mm = p.match(/([\d.,]+\s*[kmb]?)\s*(.+)/i);
                if (!mm) return;
                const n = numFromStr(mm[1]);
                const lbl = mm[2];
                if      (/repl/.test(lbl)   || /رد/.test(lbl))    comments = Math.max(comments, n);
                else if (/repost/.test(lbl) || /إعاد/.test(lbl)) retweets = Math.max(retweets, n);
                else if (/like/.test(lbl)   || /إعجاب/.test(lbl)) likes    = Math.max(likes, n);
                else if (/view/.test(lbl)   || /مشاهد/.test(lbl)) views    = Math.max(views, n);
            });
        }

        results.push({
            id: m[2],
            author: m[1],
            created_at: timeEl.getAttribute('datetime') || '',
            caption: getOriginalCaption(art),
            comments: comments,
            retweets: retweets,
            likes:    likes,
            views:    views,
            images: images,
        });
    }
    return results;
    """

    def _parse_num(txt):
        t = (txt or "").strip().replace(",", "")
        if not t:
            return 0
        try:
            if t.lower().endswith("k"): return int(float(t[:-1]) * 1000)
            if t.lower().endswith("m"): return int(float(t[:-1]) * 1000000)
            if t.lower().endswith("b"): return int(float(t[:-1]) * 1000000000)
            return int(float(t))
        except Exception:
            return 0

    def _absorb(raw_list, collected):
        """Convert JS-extracted rows into post dicts and add them to `collected`."""
        for r in raw_list:
            tid = r.get("id")
            if not tid or tid in collected:
                continue
            author = r.get("author") or "user"
            caption = r.get("caption") or ""

            # Counts come straight from each button's aria-label (already parsed in JS)
            likes    = int(r.get("likes")    or 0)
            retweets = int(r.get("retweets") or 0)
            comments = int(r.get("comments") or 0)
            views    = int(r.get("views")    or 0)

            # images: bump to large quality
            image_urls = []
            for src in r.get("images", []):
                hq = re.sub(r"&name=\w+", "&name=large", src)
                if "name=" not in hq:
                    sep = "&" if "?" in hq else "?"
                    hq = f"{hq}{sep}name=large"
                if hq not in image_urls:
                    image_urls.append(hq)

            created_at = r.get("created_at") or ""
            dt = None
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except Exception:
                    pass

            collected[tid] = {
                "username": author,
                "post_url": f"https://x.com/{author}/status/{tid}",
                "caption":  caption,
                "likes":    likes,
                "retweets": retweets,
                "comments": comments,
                "views":    views,
                "image_urls": image_urls,
                "video_urls": [],
                "post_type": "post",
                "is_retweet": False,
                "is_quote":   False,
                "has_video":  False,
                "quoted_author": "",
                "quoted_caption": "",
                "created_at": created_at,
                "_dt": dt,
            }

    collected = {}
    last_h = driver.execute_script("return document.body.scrollHeight")
    stagnant = 0

    # First extraction before any scrolling
    try:
        raw = driver.execute_script(EXTRACT_JS) or []
        _absorb(raw, collected)
    except Exception:
        pass

    # Scroll until we have `limit` posts (or until X stops loading new ones)
    max_scrolls = max(30, min(250, limit // 6 + 25))
    consecutive_no_new = 0

    for _ in range(max_scrolls):
        if len(collected) >= limit:
            break

        prev_count = len(collected)

        # Aggressive scroll: jump 4 viewports at once for max bandwidth efficiency
        driver.execute_script("window.scrollBy(0, window.innerHeight*4);")
        time.sleep(0.25)  # short pause for X to start loading

        # Extract whatever is currently rendered
        try:
            raw = driver.execute_script(EXTRACT_JS) or []
            _absorb(raw, collected)
        except Exception:
            pass

        # Track if no new posts came in
        if len(collected) == prev_count:
            consecutive_no_new += 1
            if consecutive_no_new == 1:
                time.sleep(0.6)   # first miss → wait for X to load
            elif consecutive_no_new == 2:
                time.sleep(1.0)   # try once more
            elif consecutive_no_new >= 3:
                # Final attempt: scroll back up then down to trigger lazy load
                driver.execute_script("window.scrollBy(0, -200);")
                time.sleep(0.3)
                driver.execute_script("window.scrollBy(0, window.innerHeight*5);")
                time.sleep(1.0)
                try:
                    raw = driver.execute_script(EXTRACT_JS) or []
                    before = len(collected)
                    _absorb(raw, collected)
                    if len(collected) == before:
                        break  # truly no more content
                except Exception:
                    break
                consecutive_no_new = 0
        else:
            consecutive_no_new = 0

    return list(collected.values())


def search_posts(query, limit=10, date_filter="all",
                 specific_date=None, start_date=None, end_date=None,
                 mode="keyword"):
    """
    Search X for posts by keyword or hashtag.
    mode: 'keyword' | 'hashtag'
    Uses Selenium (X's SearchTimeline GraphQL endpoint is no longer public).
    """
    query = (query or "").strip()
    if not query:
        return {"error": "Query is required", "posts": []}

    if mode == "hashtag":
        query = query.lstrip("#")

    cache_key = f"search|{mode}|{query.lower()}|{limit}|{date_filter}|{specific_date}|{start_date}|{end_date}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Convert filter params into X's since/until (YYYY-MM-DD)
    since_iso = until_iso = None
    if specific_date:
        since_iso = specific_date
        # X's `until:` is exclusive, so we add one day in the date filter logic later
        try:
            d = datetime.strptime(specific_date, "%Y-%m-%d") + timedelta(days=1)
            until_iso = d.strftime("%Y-%m-%d")
        except Exception:
            pass
    else:
        if start_date and end_date:
            # auto-swap if reversed (matches get_date_range behaviour)
            try:
                a = datetime.strptime(start_date, "%Y-%m-%d")
                b = datetime.strptime(end_date, "%Y-%m-%d")
                if a > b:
                    start_date, end_date = end_date, start_date
            except Exception:
                pass
        if start_date:
            since_iso = start_date
        if end_date:
            try:
                d = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                until_iso = d.strftime("%Y-%m-%d")
            except Exception:
                pass

    # ─── SMART DATE-RANGE DISTRIBUTION ────────────────────────────────
    # If user picks a long range (e.g. 6 months), X "Latest" only returns
    # the newest tweets — we'd never get coverage from earlier months.
    # Solution: split the range into chunks (~1 month each) and fetch
    # `limit / num_chunks` posts per chunk.
    chunks = []  # list of (since_iso, until_iso, label)
    try:
        if since_iso and until_iso:
            s = datetime.strptime(since_iso, "%Y-%m-%d")
            u = datetime.strptime(until_iso, "%Y-%m-%d")
            total_days = (u - s).days
            if total_days > 35:
                # Split into ~30-day chunks (working BACKWARDS from newest)
                cur_end = u
                while cur_end > s:
                    cur_start = max(s, cur_end - timedelta(days=30))
                    chunks.append((
                        cur_start.strftime("%Y-%m-%d"),
                        cur_end.strftime("%Y-%m-%d"),
                        f"{cur_start.strftime('%Y-%m-%d')}..{cur_end.strftime('%Y-%m-%d')}",
                    ))
                    cur_end = cur_start
    except Exception:
        chunks = []

    if not chunks:
        chunks = [(since_iso, until_iso, "single")]

    print(f"[search_posts] Splitting into {len(chunks)} chunk(s) for {limit} posts")

    # Per-chunk target: distribute evenly + 30% buffer for filtering/dedup
    per_chunk = max(5, int((limit / len(chunks)) * 1.3))

    posts_by_id = {}
    fetch_error = None

    # ─── SEQUENTIAL CHUNK EXECUTION (one shared driver) ──────────────
    # We tried 3-way parallel drivers; X flagged the account as bot
    # activity ("verify you are not a robot" page) within 30 seconds.
    # Running chunks sequentially through a single warmed driver is
    # the only reliable pattern for now.
    for chunk_idx, (c_since, c_until, label) in enumerate(chunks):
        if len(posts_by_id) >= limit:
            break
        print(f"[chunk {chunk_idx+1}/{len(chunks)}] {label} -> target {per_chunk}")
        try:
            chunk_raw = _selenium_search(
                query, limit=per_chunk, mode=mode,
                since_date=c_since, until_date=c_until,
            )
        except Exception as e:
            print(f"[chunk {chunk_idx+1}] error: {e}")
            fetch_error = str(e)
            continue

        new_in_chunk = 0
        for p in chunk_raw:
            pid = p.get("post_url", "").split("/")[-1]
            if pid and pid not in posts_by_id:
                posts_by_id[pid] = p
                new_in_chunk += 1
        print(f"[chunk {chunk_idx+1}/{len(chunks)}] +{new_in_chunk} new (total={len(posts_by_id)})")

    if not posts_by_id and fetch_error:
        return {"error": "تعذر إجراء البحث. تأكد من تثبيت Chrome.", "posts": []}

    # Apply date filters (just in case X returns posts outside the range)
    range_start, range_end = get_date_range(specific_date, start_date, end_date)
    threshold = None if (range_start or range_end) else get_date_threshold(date_filter)

    filtered = []
    for p in posts_by_id.values():
        dt = p.get("_dt")
        if not _matches(dt, threshold, range_start, range_end):
            continue
        clean = {k: v for k, v in p.items() if not k.startswith("_")}
        filtered.append((dt, clean))

    filtered.sort(key=lambda x: x[0] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    posts = [p for _, p in filtered[:limit]]

    print(f"[search_posts] Collected {len(posts)} posts (target was {limit})")

    # ─── Replace captions with ORIGINAL language via Syndication CDN ─────
    # This bypasses X's account-level auto-translate (which replaces tweet
    # text with the translation in the DOM). Runs in parallel threads.
    if posts:
        print(f"[search_posts] Fetching original captions for {len(posts)} posts...")
        try:
            _enrich_with_originals(posts, max_workers=15)
        except Exception as e:
            print(f"[search_posts] enrich error: {e}")

    final = {"error": None, "posts": posts}
    _cache_set(cache_key, final)
    return final


def get_posts(username, limit=10, date_filter="all",
              specific_date=None, start_date=None, end_date=None):
    username = username.strip().lstrip("@")
    if not username:
        return {"error": "Username is required", "posts": []}

    cache_key = f"{username.lower()}|{limit}|{date_filter}|{specific_date}|{start_date}|{end_date}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    all_posts, err = _fetch_all_posts_for_user(username, target_count=limit)

    if err == "suspended":
        return {"error": "الحساب موقوف (Suspended)", "posts": []}
    if err == "not_found":
        return {"error": "الحساب غير موجود", "posts": []}
    if err == "protected":
        return {"error": "الحساب خاص (Protected)", "posts": []}

    if (not all_posts) or all_posts is None:
        stale = _TWEETS_CACHE.get(username.lower())
        if stale and stale[1]:
            all_posts = stale[1]
        else:
            return {
                "error": "X لم يستجب. اضغط 'ابدأ الاستخراج' مرة أخرى خلال 30 ثانية.",
                "posts": []
            }

    range_start, range_end = get_date_range(specific_date, start_date, end_date)
    threshold = None if (range_start or range_end) else get_date_threshold(date_filter)

    filtered = []
    for p in all_posts:
        dt = p.get("_dt")
        if not _matches(dt, threshold, range_start, range_end):
            continue
        clean = {k: v for k, v in p.items() if not k.startswith("_")}
        filtered.append(clean)

    posts_out = filtered[:limit]

    # ─── Enrich with Syndication CDN ──────────────────────────────────
    # Fixes two things for fresh tweets:
    #   1. Original (untranslated) caption text
    #   2. Accurate like/reply/retweet/view counts (DOM often shows 0
    #      for tweets posted minutes ago because counter spans haven't
    #      rendered yet — the CDN returns the real numbers).
    if posts_out:
        try:
            _enrich_with_originals(posts_out, max_workers=15)
        except Exception as e:
            print(f"[get_posts] enrich error: {e}")

    final = {"error": None, "posts": posts_out}
    _cache_set(cache_key, final)
    return final
