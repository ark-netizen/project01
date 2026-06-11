import os
import re
import json
import uuid
import base64
import secrets
import asyncio
import threading
import importlib

try:
    from curl_cffi import requests as curl_req
    _USE_CURL = True
except ImportError:
    import requests as curl_req  # type: ignore[no-redef]
    _USE_CURL = False

# Try every known location for twikit's ClientTransaction
_CTClass = None
for _mod_path, _cls_name in [
    ("twikit._core.utils", "ClientTransaction"),
    ("twikit.utils",       "ClientTransaction"),
    ("twikit._core",       "ClientTransaction"),
    ("twikit",             "ClientTransaction"),
]:
    try:
        _m = importlib.import_module(_mod_path)
        _c = getattr(_m, _cls_name, None)
        if _c is not None:
            _CTClass = _c
            break
    except Exception:
        pass

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

_live_qid: str | None = None
_guest_token: str | None = None
_ct_obj = None
_ct_info: str = "not_init"
_qid_lock = threading.Lock()
_CLIENT_UUID = str(uuid.uuid4())


def _redact(msg: str) -> str:
    for val in (_auth_token, _ct0):
        if val and val in msg:
            msg = msg.replace(val, "[REDACTED]")
    return msg


# ─── guest token ──────────────────────────────────────────────────

def _activate_guest_token() -> str | None:
    """GET a guest token from api.twitter.com — required for session init."""
    if not _USE_CURL:
        return None
    try:
        r = curl_req.post(
            "https://api.twitter.com/1.1/guest/activate.json",
            headers={"Authorization": f"Bearer {_BEARER}"},
            impersonate="chrome120",
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("guest_token")
    except Exception:
        pass
    return None


# ─── ClientTransaction (twikit) ───────────────────────────────────

class _FakeResp:
    def __init__(self, text: str):
        self.text = text


def _init_ct() -> None:
    global _ct_obj, _ct_info
    if not (_CTClass and _USE_CURL):
        _ct_info = f"no_CT(twikit={bool(_CTClass)},curl={_USE_CURL})"
        return
    try:
        r = curl_req.get(
            "https://x.com/",
            headers={"Accept": "text/html,*/*", "Accept-Language": "en-US,en;q=0.9",
                     "Cache-Control": "no-cache"},
            impersonate="chrome120", timeout=20,
        )
        _ct_obj = _CTClass(_FakeResp(r.text))
        _ct_info = "CT_OK"
    except Exception as e:
        _ct_info = f"CT_err:{str(e)[:50]}"


def _txn_id(method: str, path: str) -> str:
    if _ct_obj is not None:
        try:
            return _ct_obj.generate_transaction_id(method, path)
        except Exception:
            pass
    return base64.b64encode(secrets.token_bytes(30)).decode().rstrip("=")


# ─── query-id detection ───────────────────────────────────────────

def _find_qid(text: str) -> str | None:
    m = re.search(
        r'/i/api/graphql/([A-Za-z0-9_-]{15,})/SearchTimeline(?![A-Za-z])', text)
    if m:
        return m.group(1)
    for pat in (
        r'queryId:"([A-Za-z0-9_-]{15,})"[^}]{0,250}operationName:"SearchTimeline"(?![A-Za-z])',
        r'"queryId":"([A-Za-z0-9_-]{15,})"[^}]{0,250}"operationName":"SearchTimeline"(?![A-Za-z])',
    ):
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


def _fetch_qid() -> tuple[str | None, str]:
    if not _USE_CURL:
        return None, "no curl_cffi"
    ck = {"impersonate": "chrome120"}
    debug: list[str] = []
    try:
        page = curl_req.get(
            "https://x.com/",
            headers={"Accept": "text/html,*/*", "Cache-Control": "no-cache"},
            timeout=20, **ck,
        )
        html = page.text or ""
        debug.append(f"html={len(html)}")
        qid = _find_qid(html)
        if qid:
            return qid, "html"
        urls = list(dict.fromkeys(re.findall(
            r'https://abs\.twimg\.com/responsive-web/client-web/[^\s"\'<>]+\.js', html)))
        urls.sort(key=lambda u: (0 if any(k in u for k in ("main", "api")) else 1))
        debug.append(f"bundles={len(urls)}")
        for u in urls[:25]:
            try:
                jr = curl_req.get(u, timeout=15, **ck)
                txt = jr.text or ""
                if len(txt) < 1000:
                    continue
                qid = _find_qid(txt)
                if qid:
                    return qid, u.split("/")[-1][:30]
            except Exception:
                continue
        debug.append("not_found")
    except Exception as e:
        debug.append(str(e)[:50])
    return None, "; ".join(debug)


async def initialize() -> None:
    global _auth_token, _ct0, _live_qid
    _auth_token = os.getenv("TWITTER_AUTH_TOKEN", "").strip()
    _ct0 = os.getenv("TWITTER_CT0", "").strip()
    manual = os.getenv("TWITTER_SEARCH_QID", "").strip()
    if manual:
        _live_qid = manual
    asyncio.get_event_loop().run_in_executor(None, _warm)


def _warm() -> None:
    global _live_qid, _guest_token
    _init_ct()
    gt = _activate_guest_token()
    if gt:
        _guest_token = gt
    if not _live_qid:
        with _qid_lock:
            if not _live_qid:
                qid, _ = _fetch_qid()
                if qid:
                    _live_qid = qid


def is_ready() -> bool:
    return bool(_auth_token and _ct0)


# ─── response parsing ─────────────────────────────────────────────

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
            entries = inst.get("entries", [])
        elif t == "TimelineAddToModule":
            entries = inst.get("moduleItems", [])
        else:
            continue
        for entry in entries:
            content = entry.get("content") or entry.get("item") or {}
            ic = content.get("itemContent", {})
            if ic.get("itemType") != "TimelineTweet":
                continue
            result = ic.get("tweet_results", {}).get("result", {})
            if not result:
                continue
            if result.get("__typename") == "TweetWithVisibilityResults":
                result = result.get("tweet", result)
            leg = result.get("legacy", {})
            uleg = (result.get("core", {})
                         .get("user_results", {})
                         .get("result", {})
                         .get("legacy", {}))
            if not leg:
                continue
            tweets.append({
                "id": leg.get("id_str", ""),
                "text": leg.get("full_text") or leg.get("text", ""),
                "user": uleg.get("screen_name", "unknown"),
                "created_at": leg.get("created_at", ""),
                "likes": leg.get("favorite_count", 0),
                "retweets": leg.get("retweet_count", 0),
            })
    return tweets if tweets else None


# ─── search ───────────────────────────────────────────────────────

_BASES = [
    "https://x.com/i/api/graphql",
    "https://twitter.com/i/api/graphql",
]


def _try(qid: str, base: str, headers: dict, cookies: dict,
         variables: str, feats: bool = True) -> list[dict] | str:
    url = f"{base}/{qid}/SearchTimeline"
    short = url.replace("https://", "").replace("twitter.com", "tw.com")[:48]
    ck = {"impersonate": "chrome120"} if _USE_CURL else {}
    params: dict = {"variables": variables}
    if feats:
        params["features"] = _FEATURES
        params["fieldToggles"] = _FIELD_TOGGLES
    try:
        r = curl_req.get(url, headers=headers, cookies=cookies,
                         params=params, timeout=15, **ck)
        s = r.status_code
        if s == 404:
            return f"[{short}] 404"
        if s in (401, 403):
            return f"[{short}] 인증오류({s})"
        if s == 429:
            raise RuntimeError("Twitter 요청 한도 초과: 잠시 후 다시 시도해주세요.")
        if not r.content or not r.content.strip():
            return f"[{short}] 빈응답({s})"
        try:
            data = r.json()
        except ValueError:
            return f"[{short}] JSON오류({s}): {r.text[:60]}"
        if "errors" in data and data["errors"]:
            msgs = "; ".join(e.get("message", "?")[:40] for e in data["errors"][:2])
            return f"[{short}] API오류({s}): {msgs}"
        tweets = _parse_graphql(data)
        if tweets is not None:
            return tweets
        if "data" in data:
            return []
        return f"[{short}] 파싱실패({s}) keys={list(data.keys())[:4]}"
    except RuntimeError:
        raise
    except Exception as e:
        return f"[{short}] 예외: {_redact(str(e))[:80]}"


def _search_sync(keyword: str, count: int) -> list[dict]:
    global _live_qid, _guest_token

    qids: list[str] = []
    if _live_qid:
        qids.append(_live_qid)
    for q in _FALLBACK_QIDS:
        if q not in qids:
            qids.append(q)

    errors: list[str] = []
    all_404 = True

    # Refresh guest token if missing
    if not _guest_token:
        gt = _activate_guest_token()
        if gt:
            _guest_token = gt

    for qid in qids:
        path = f"/i/api/graphql/{qid}/SearchTimeline"
        headers = {
            "Authorization": f"Bearer {_BEARER}",
            "x-csrf-token": _ct0,
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-client-language": "ko",
            "x-client-uuid": _CLIENT_UUID,
            "x-client-transaction-id": _txn_id("GET", path),
            "Accept": "*/*",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://x.com/search",
            "Origin": "https://x.com",
        }
        if _guest_token:
            headers["x-guest-token"] = _guest_token
        cookies = {"auth_token": _auth_token, "ct0": _ct0}
        variables = json.dumps({
            "rawQuery": keyword,
            "count": count,
            "querySource": "typed_query",
            "product": "Latest",
        }, separators=(',', ':'))

        for base in _BASES:
            res = _try(qid, base, headers, cookies, variables)
            if isinstance(res, list):
                return res
            errors.append(res)
            if "404" not in res:
                all_404 = False

    # All 404 → fresh qid fetch
    if all_404:
        fresh, dbg = _fetch_qid()
        if fresh and fresh not in qids:
            with _qid_lock:
                _live_qid = fresh
            errors.append(f"[fresh:{fresh[:8]}@{dbg}]")
            path = f"/i/api/graphql/{fresh}/SearchTimeline"
            headers["x-client-transaction-id"] = _txn_id("GET", path)
            for base in _BASES:
                res = _try(fresh, base, headers, cookies, variables)
                if isinstance(res, list):
                    return res
                errors.append(res)
        else:
            errors.append(f"[same_qid:{dbg}]")

    raise RuntimeError(
        f"Twitter 검색 실패 (curl={'on' if _USE_CURL else 'off'},CT={_ct_info},"
        f"gt={'on' if _guest_token else 'off'}): " + " / ".join(errors)
    )


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
