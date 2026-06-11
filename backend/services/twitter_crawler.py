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

# (queryId, graphql_base_url)
_live: tuple[str, str] | None = None
_qid_lock = threading.Lock()


def _redact(msg: str) -> str:
    for val in (_auth_token, _ct0):
        if val and val in msg:
            msg = msg.replace(val, "[REDACTED]")
    return msg


# ------------------------------------------------------------------
# Query-ID detection: finds the SearchTimeline queryId AND base URL
# from x.com JS bundles.
#
# Bug in previous version: reverse regex (operationName→queryId)
# spanned object boundaries in minified JS and matched the NEXT
# operation's queryId.  Now only forward (queryId→operationName).
# ------------------------------------------------------------------

def _find_in_text(text: str) -> tuple[str, str] | None:
    """
    Returns (queryId, graphql_base_url) or None.
    graphql_base_url example: "https://x.com/i/api/graphql"
    """
    # ── Pattern 1: full HTTPS URL (most reliable, exact base captured)
    m = re.search(
        r'(https://[a-z0-9.-]+(?:/i/api)?/graphql)/([A-Za-z0-9_-]{15,})/SearchTimeline',
        text,
    )
    if m:
        return m.group(2), m.group(1)   # (qid, base)

    # ── Pattern 2: absolute path only  /i/api/graphql/QID/SearchTimeline
    #              or                   /graphql/QID/SearchTimeline
    m = re.search(
        r'((?:/i/api)?/graphql)/([A-Za-z0-9_-]{15,})/SearchTimeline',
        text,
    )
    if m:
        path_prefix = m.group(1)        # "/i/api/graphql" or "/graphql"
        qid = m.group(2)
        base = "https://x.com" + path_prefix
        return qid, base

    # ── Pattern 3: queryId BEFORE operationName  (forward only — no reverse)
    #   Reverse pattern was matching the NEXT operation's ID in minified JS.
    for pat in (
        r'queryId:"([A-Za-z0-9_-]{15,})"[^}]{0,200}operationName:"SearchTimeline"',
        r'"queryId":"([A-Za-z0-9_-]{15,})"[^}]{0,200}"operationName":"SearchTimeline"',
    ):
        m = re.search(pat, text)
        if m:
            return m.group(1), "https://x.com/i/api/graphql"

    return None


def _fetch_live() -> tuple[tuple[str, str] | None, str]:
    """Returns ((queryId, base_url), debug_info)."""
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
        debug.append(f"html={len(html)}")

        result = _find_in_text(html)
        if result:
            return result, f"found in HTML"

        js_urls: list[str] = list(dict.fromkeys(
            re.findall(r'https://abs\.twimg\.com/responsive-web/client-web/[^\s"\'<>]+\.js', html)
        ))
        js_urls.sort(key=lambda u: (0 if any(k in u for k in ("main", "api", "bundle")) else 1))
        debug.append(f"bundles={len(js_urls)}")

        for js_url in js_urls[:20]:
            try:
                jr = curl_req.get(js_url, timeout=15, **curl_kw)
                text = jr.text or ""
                if len(text) < 1000:
                    continue
                result = _find_in_text(text)
                if result:
                    fname = js_url.split("/")[-1][:35]
                    return result, f"found in {fname}"
            except Exception as e:
                debug.append(f"jserr:{str(e)[:30]}")
                continue

        debug.append("not found in any bundle")
    except Exception as e:
        debug.append(f"err:{str(e)[:60]}")
    return None, "; ".join(debug)


async def initialize() -> None:
    global _auth_token, _ct0
    _auth_token = os.getenv("TWITTER_AUTH_TOKEN", "").strip()
    _ct0 = os.getenv("TWITTER_CT0", "").strip()
    asyncio.get_event_loop().run_in_executor(None, _warm)


def _warm() -> None:
    global _live
    with _qid_lock:
        if _live:
            return
        result, _ = _fetch_live()
        if result:
            _live = result


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


def _try_one(qid: str, base_url: str, headers: dict, cookies: dict,
             variables: str, features: str | None = _FEATURES) -> list[dict] | str:
    url = f"{base_url}/{qid}/SearchTimeline"
    tag = f"[{qid[:8]}@{base_url.split('/')[2][:8]}]"
    curl_kw = {"impersonate": "chrome120"} if _USE_CURL else {}
    try:
        params: dict = {"variables": variables}
        if features is not None:
            params["features"] = features
            params["fieldToggles"] = _FIELD_TOGGLES
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
    global _live

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

    errors: list[str] = []

    # 1. Try live qid with its detected base URL
    if _live:
        qid, base = _live
        res = _try_one(qid, base, headers, cookies, variables)
        if isinstance(res, list):
            return res
        errors.append(res)
        # Also try with the other domain
        alt = base.replace("x.com", "twitter.com") if "x.com" in base else base.replace("twitter.com", "x.com")
        if alt != base:
            res2 = _try_one(qid, alt, headers, cookies, variables)
            if isinstance(res2, list):
                return res2
            errors.append(res2)

    # 2. Try fallback qids on standard bases
    for qid in _FALLBACK_QIDS:
        if _live and qid == _live[0]:
            continue
        for base in ("https://x.com/i/api/graphql", "https://twitter.com/i/api/graphql"):
            res = _try_one(qid, base, headers, cookies, variables)
            if isinstance(res, list):
                return res
            errors.append(res)

    # 3. All 404 — fetch fresh and retry
    if all("404" in e for e in errors):
        fresh, dbg = _fetch_live()
        if fresh and fresh != _live:
            with _qid_lock:
                _live = fresh
            qid, base = fresh
            errors.append(f"fresh={qid[:8]}@{dbg}")
            res = _try_one(qid, base, headers, cookies, variables)
            if isinstance(res, list):
                return res
            errors.append(res)
            # Also try without features (in case features flags are outdated)
            res2 = _try_one(qid, base, headers, cookies, variables, features=None)
            if isinstance(res2, list):
                return res2
            errors.append(f"no-features:{res2}")
        else:
            errors.append(f"fetch_fail={dbg}")

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
