import os
import re
import json
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

# Fallback query IDs (may be outdated — live fetch is preferred)
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

_live_qid: str | None = None
_live_qid_debug: str = ""
_qid_lock = threading.Lock()


def _redact(msg: str) -> str:
    for val in (_auth_token, _ct0):
        if val and val in msg:
            msg = msg.replace(val, "[REDACTED]")
    return msg


def _find_search_qid(text: str) -> str | None:
    """Find SearchTimeline query ID from JS/HTML text."""
    # Most reliable: the full constructed URL appears in the JS
    for m in re.finditer(r'/graphql/([A-Za-z0-9_-]{15,})/SearchTimeline', text):
        return m.group(1)

    # queryId value immediately adjacent to operationName:"SearchTimeline"
    for pat in (
        r'"queryId"\s*:\s*"([A-Za-z0-9_-]{15,})"[^}]{0,500}"operationName"\s*:\s*"SearchTimeline"',
        r'"operationName"\s*:\s*"SearchTimeline"[^}]{0,500}"queryId"\s*:\s*"([A-Za-z0-9_-]{15,})"',
        r'queryId:"([A-Za-z0-9_-]{15,})"[^}]{0,500}operationName:"SearchTimeline"',
        r'operationName:"SearchTimeline"[^}]{0,500}queryId:"([A-Za-z0-9_-]{15,})"',
    ):
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


def _fetch_live_query_id() -> tuple[str | None, str]:
    """Returns (queryId, debug_info). Fetches from x.com JS bundles."""
    if not _USE_CURL:
        return None, "curl_cffi not available"
    curl_kw = {"impersonate": "chrome120"}
    debug: list[str] = []
    try:
        page = curl_req.get(
            "https://x.com/",
            headers={"Accept": "text/html,application/xhtml+xml,*/*",
                     "Accept-Language": "en-US,en;q=0.9"},
            timeout=20, **curl_kw,
        )
        html = page.text or ""
        debug.append(f"html={len(html)}chars")

        # Check directly in HTML first
        qid = _find_search_qid(html)
        if qid:
            return qid, f"found in HTML"

        # Collect JS bundle URLs
        js_urls: list[str] = list(dict.fromkeys(
            re.findall(r'https://abs\.twimg\.com/responsive-web/client-web/[^\s"\'<>]+\.js', html)
        ))
        # Prefer bundles likely to have API code
        js_urls.sort(key=lambda u: (0 if any(k in u for k in ("main", "api", "bundle")) else 1))
        debug.append(f"bundles={len(js_urls)}")

        for js_url in js_urls[:20]:
            try:
                jr = curl_req.get(js_url, timeout=15, **curl_kw)
                text = jr.text or ""
                if len(text) < 1000:
                    continue
                qid = _find_search_qid(text)
                if qid:
                    fname = js_url.split("/")[-1][:30]
                    return qid, f"found in {fname}"
            except Exception as e:
                debug.append(f"js_err:{str(e)[:30]}")
                continue

        debug.append("not found in any bundle")
    except Exception as e:
        debug.append(f"page_err:{str(e)[:60]}")
    return None, "; ".join(debug)


async def initialize() -> None:
    global _auth_token, _ct0
    _auth_token = os.getenv("TWITTER_AUTH_TOKEN", "").strip()
    _ct0 = os.getenv("TWITTER_CT0", "").strip()
    asyncio.get_event_loop().run_in_executor(None, _warm_query_id)


def _warm_query_id() -> None:
    global _live_qid, _live_qid_debug
    with _qid_lock:
        if _live_qid:
            return
        qid, dbg = _fetch_live_query_id()
        _live_qid_debug = dbg
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


def _try_qid(qid: str, base: str, headers: dict, cookies: dict, variables: str) -> list[dict] | str:
    url = f"{base}/i/api/graphql/{qid}/SearchTimeline"
    tag = f"[{base.split('/')[2][:5]}:{qid[:8]}]"
    curl_kw = {"impersonate": "chrome120"} if _USE_CURL else {}
    try:
        r = curl_req.get(
            url, headers=headers, cookies=cookies,
            params={"variables": variables, "features": _FEATURES, "fieldToggles": _FIELD_TOGGLES},
            timeout=15, **curl_kw,
        )
        status = r.status_code
        if status == 404:
            return f"{tag} qid만료(404)"
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
            return f"{tag} API오류: {msgs}"

        tweets = _parse_graphql(data)
        if tweets is not None:
            return tweets
        if "data" in data:
            return []
        return f"{tag} 파싱실패 keys={list(data.keys())[:4]}"
    except RuntimeError:
        raise
    except Exception as e:
        return f"{tag} 예외: {_redact(str(e))[:80]}"


def _search_sync(keyword: str, count: int) -> list[dict]:
    global _live_qid, _live_qid_debug

    headers = {
        "Authorization": f"Bearer {_BEARER}",
        "x-csrf-token": _ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-client-language": "ko",
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

    qids = []
    if _live_qid:
        qids.append(_live_qid)
    for q in _FALLBACK_QIDS:
        if q not in qids:
            qids.append(q)

    errors = []
    all_404 = True
    for qid in qids:
        for base in ("https://x.com", "https://twitter.com"):
            res = _try_qid(qid, base, headers, cookies, variables)
            if isinstance(res, list):
                return res
            errors.append(res)
            if "qid만료(404)" not in res:
                all_404 = False

    # All 404 — try fresh live fetch
    if all_404:
        fresh, dbg = _fetch_live_query_id()
        _live_qid_debug = dbg
        if fresh and fresh not in qids:
            with _qid_lock:
                _live_qid = fresh
            for base in ("https://x.com", "https://twitter.com"):
                res = _try_qid(fresh, base, headers, cookies, variables)
                if isinstance(res, list):
                    return res
                errors.append(f"[fresh:{fresh[:8]}] {res}")
        else:
            errors.append(f"live_fetch={dbg}")

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
