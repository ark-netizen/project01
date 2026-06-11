import os
import re
import json
import uuid
import base64
import secrets
import asyncio
import threading

try:
    from curl_cffi import requests as curl_req
    _USE_CURL = True
except ImportError:
    import requests as curl_req  # type: ignore[no-redef]
    _USE_CURL = False

_auth_token: str = ""
_ct0: str = ""
MAX_COUNT = 50

_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

_FALLBACK_QIDS = [
    "nK1dw4oV3k4w5TdtcAdSww",
    "gkjsKepM6gl_HmFWoWKfgg",
    "7jMcZ7NW_rL6MHT9WnRFkg",
]

_FEATURES = json.dumps({
    "rweb_lists_timeline_redesign_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": False,
    "tweet_awards_web_tipping_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_media_download_video_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
}, separators=(',', ':'))

_FIELD_TOGGLES = json.dumps({"withArticleRichContentState": False}, separators=(',', ':'))

# Cached live query ID
_live_qid: str | None = None
_qid_lock = threading.Lock()
# Stable session UUID (generated once, reused per process lifetime)
_CLIENT_UUID = str(uuid.uuid4())


def _redact(msg: str) -> str:
    for val in (_auth_token, _ct0):
        if val and val in msg:
            msg = msg.replace(val, "[REDACTED]")
    return msg


def _rand_txn_id() -> str:
    """Generate a plausible-looking x-client-transaction-id."""
    return base64.b64encode(secrets.token_bytes(30)).decode().rstrip("=")


def _find_qid_in_text(text: str) -> str | None:
    """
    Extract SearchTimeline queryId from JS/HTML text.
    Uses (?![A-Za-z]) boundary to avoid matching 'SearchTimelineXxx'.
    Uses ONLY forward patterns (queryId→operationName) — never reverse.
    Always forces /i/api/graphql base (ignores /graphql without /i/api).
    """
    # Highest confidence: full /i/api/graphql URL with SearchTimeline
    m = re.search(
        r'/i/api/graphql/([A-Za-z0-9_-]{15,})/SearchTimeline(?![A-Za-z])',
        text,
    )
    if m:
        return m.group(1)

    # queryId immediately before operationName:"SearchTimeline" (forward only)
    for pat in (
        r'queryId:"([A-Za-z0-9_-]{15,})"[^}]{0,250}operationName:"SearchTimeline"(?![A-Za-z])',
        r'"queryId"\s*:\s*"([A-Za-z0-9_-]{15,})"[^}]{0,250}"operationName"\s*:\s*"SearchTimeline"(?![A-Za-z])',
    ):
        m = re.search(pat, text)
        if m:
            return m.group(1)

    return None


def _fetch_live_qid() -> tuple[str | None, str]:
    """Returns (queryId, debug_info)."""
    if not _USE_CURL:
        return None, "curl_cffi not installed"
    curl_kw = {"impersonate": "chrome120"}
    debug: list[str] = []
    try:
        page = curl_req.get(
            "https://x.com/",
            headers={
                "Accept": "text/html,application/xhtml+xml,*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
            timeout=20, **curl_kw,
        )
        html = page.text or ""
        debug.append(f"html={len(html)}")

        qid = _find_qid_in_text(html)
        if qid:
            return qid, "found_in_html"

        js_urls: list[str] = list(dict.fromkeys(
            re.findall(
                r'https://abs\.twimg\.com/responsive-web/client-web/[^\s"\'<>]+\.js',
                html,
            )
        ))
        # Prefer bundles likely to contain API definitions
        js_urls.sort(key=lambda u: (0 if any(k in u for k in ("main", "api", "bundle")) else 1))
        debug.append(f"bundles={len(js_urls)}")

        for js_url in js_urls[:20]:
            try:
                jr = curl_req.get(js_url, timeout=15, **curl_kw)
                text = jr.text or ""
                if len(text) < 1000:
                    continue
                qid = _find_qid_in_text(text)
                if qid:
                    fname = js_url.split("/")[-1][:35]
                    return qid, f"found_in_{fname}"
            except Exception as e:
                debug.append(f"js_err:{str(e)[:25]}")
                continue

        debug.append("not_found_in_any_bundle")
    except Exception as e:
        debug.append(f"page_err:{str(e)[:50]}")
    return None, "; ".join(debug)


async def initialize() -> None:
    global _auth_token, _ct0
    _auth_token = os.getenv("TWITTER_AUTH_TOKEN", "").strip()
    _ct0 = os.getenv("TWITTER_CT0", "").strip()
    asyncio.get_event_loop().run_in_executor(None, _warm)


def _warm() -> None:
    global _live_qid
    with _qid_lock:
        if _live_qid:
            return
        qid, _ = _fetch_live_qid()
        if qid:
            _live_qid = qid


def is_ready() -> bool:
    return bool(_auth_token and _ct0)


def _parse_graphql(data: dict) -> list[dict] | None:
    try:
        instructions = (
            data["data"]["search_by_raw_query"]["search_timeline"]["timeline"]["instructions"]
        )
    except (KeyError, TypeError):
        return None

    tweets = []
    for inst in instructions:
        t = inst.get("type", "")
        if t == "TimelineAddEntries":
            raw_entries = inst.get("entries", [])
        elif t == "TimelineAddToModule":
            raw_entries = inst.get("moduleItems", [])
        else:
            continue

        for entry in raw_entries:
            content = entry.get("content") or entry.get("item") or {}
            item_content = content.get("itemContent", {})
            if item_content.get("itemType") != "TimelineTweet":
                continue

            result = item_content.get("tweet_results", {}).get("result", {})
            if not result:
                continue
            if result.get("__typename") == "TweetWithVisibilityResults":
                result = result.get("tweet", result)

            legacy = result.get("legacy", {})
            user_legacy = (
                result.get("core", {})
                      .get("user_results", {})
                      .get("result", {})
                      .get("legacy", {})
            )
            if not legacy:
                continue

            tweets.append({
                "id": legacy.get("id_str", ""),
                "text": legacy.get("full_text") or legacy.get("text", ""),
                "user": user_legacy.get("screen_name", "unknown"),
                "created_at": legacy.get("created_at", ""),
                "likes": legacy.get("favorite_count", 0),
                "retweets": legacy.get("retweet_count", 0),
            })

    return tweets if tweets else None


_GRAPHQL_BASES = [
    "https://x.com/i/api/graphql",
    "https://twitter.com/i/api/graphql",
]


def _try_one(qid: str, base: str, headers: dict, cookies: dict,
             variables: str, with_features: bool = True) -> list[dict] | str:
    url = f"{base}/{qid}/SearchTimeline"
    # Show enough of the URL to confirm the correct path is being used
    short = url.replace("https://", "").replace("twitter.com", "tw.com")[:45]
    tag = f"[{short}]"
    curl_kw = {"impersonate": "chrome120"} if _USE_CURL else {}
    params: dict = {"variables": variables}
    if with_features:
        params["features"] = _FEATURES
        params["fieldToggles"] = _FIELD_TOGGLES
    try:
        r = curl_req.get(url, headers=headers, cookies=cookies,
                         params=params, timeout=15, **curl_kw)
        status = r.status_code
        if status == 404:
            return f"{tag} 404"
        if status in (401, 403):
            return f"{tag} 인증오류({status})"
        if status == 429:
            raise RuntimeError("Twitter 요청 한도 초과: 잠시 후 다시 시도해주세요.")
        if not r.content or not r.content.strip():
            return f"{tag} 빈응답({status})"
        try:
            data = r.json()
        except ValueError:
            return f"{tag} JSON오류({status}): {r.text[:60]}"
        if "errors" in data and data["errors"]:
            msgs = "; ".join(e.get("message", "?")[:40] for e in data["errors"][:2])
            return f"{tag} API오류({status}): {msgs}"
        tweets = _parse_graphql(data)
        if tweets is not None:
            return tweets
        if "data" in data:
            return []
        return f"{tag} 파싱실패({status}) keys={list(data.keys())[:4]}"
    except RuntimeError:
        raise
    except Exception as e:
        return f"{tag} 예외: {_redact(str(e))[:80]}"


def _search_sync(keyword: str, count: int) -> list[dict]:
    global _live_qid

    headers = {
        "Authorization": f"Bearer {_BEARER}",
        "x-csrf-token": _ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-client-language": "ko",
        "x-client-uuid": _CLIENT_UUID,
        "x-client-transaction-id": _rand_txn_id(),
        "Accept": "*/*",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://x.com/search",
        "Origin": "https://x.com",
    }
    cookies = {"auth_token": _auth_token, "ct0": _ct0}
    variables = json.dumps({
        "rawQuery": keyword,
        "count": count,
        "querySource": "typed_query",
        "product": "Latest",
    }, separators=(',', ':'))

    errors: list[str] = []

    # Build ordered qid list: live first, then fallbacks
    qids: list[str] = []
    if _live_qid:
        qids.append(_live_qid)
    for q in _FALLBACK_QIDS:
        if q not in qids:
            qids.append(q)

    for qid in qids:
        for base in _GRAPHQL_BASES:
            res = _try_one(qid, base, headers, cookies, variables)
            if isinstance(res, list):
                return res
            errors.append(res)

    # All 404 → fresh fetch and retry
    if all("404" in e for e in errors):
        fresh_qid, dbg = _fetch_live_qid()
        if fresh_qid and fresh_qid not in qids:
            with _qid_lock:
                _live_qid = fresh_qid
            errors.append(f"[fresh={fresh_qid[:8]}@{dbg}]")
            for base in _GRAPHQL_BASES:
                # Try with features
                res = _try_one(fresh_qid, base, headers, cookies, variables)
                if isinstance(res, list):
                    return res
                errors.append(res)
                # Try without features (in case feature flags have changed)
                res2 = _try_one(fresh_qid, base, headers, cookies, variables, with_features=False)
                if isinstance(res2, list):
                    return res2
                errors.append(f"no-feat:{res2}")
        else:
            errors.append(f"[fresh_same_or_fail: {dbg}]")

    curl_info = f"curl={'on' if _USE_CURL else 'off'}"
    raise RuntimeError(f"Twitter 검색 실패 ({curl_info}): " + " / ".join(errors))


async def search_tweets(keyword: str, count: int = 30) -> list[dict]:
    if not is_ready():
        raise RuntimeError("Twitter 서비스가 설정되지 않았습니다.")
    count = min(count, MAX_COUNT)
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, lambda: _search_sync(keyword, count))
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(_redact(str(e)))
