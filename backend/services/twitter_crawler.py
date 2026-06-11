import os
import re
import json
import uuid
import base64
import secrets
import asyncio
import threading
import importlib
import pkgutil

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

_live_qid: str | None = None
_guest_token: str | None = None
_ct_obj = None
_CTClass = None
_ct_info: str = "not_init"
_twikit_diag: str = "not_init"
_qid_lock = threading.Lock()
_CLIENT_UUID = str(uuid.uuid4())


def _redact(msg: str) -> str:
    for val in (_auth_token, _ct0):
        if val and val in msg:
            msg = msg.replace(val, "[REDACTED]")
    return msg


# ─── twikit discovery (pkgutil full scan) ────────────────────────

def _discover_twikit() -> None:
    global _CTClass, _twikit_diag
    try:
        import twikit as _tw
        ver = getattr(_tw, "__version__", "?")
        _twikit_diag = f"v{ver}"

        # Check __init__ exports first
        ct = getattr(_tw, "ClientTransaction", None)
        if ct:
            _CTClass = ct
            _twikit_diag += ",CT@__init__"
            return

        # Walk every submodule
        found_at = None
        for _, modname, _ in pkgutil.walk_packages(
            path=_tw.__path__, prefix="twikit.", onerror=lambda _: None
        ):
            try:
                mod = importlib.import_module(modname)
                ct = getattr(mod, "ClientTransaction", None)
                if ct:
                    _CTClass = ct
                    found_at = modname
                    break
            except Exception:
                pass

        if found_at:
            _twikit_diag += f",CT@{found_at}"
        else:
            top = [a for a in dir(_tw) if not a.startswith("_")][:8]
            _twikit_diag += f",CT_not_found,top={top}"

    except ImportError as e:
        _twikit_diag = f"not_installed:{str(e)[:40]}"
    except Exception as e:
        _twikit_diag = f"err:{str(e)[:50]}"


# ─── guest token ─────────────────────────────────────────────────

def _activate_guest_token() -> str | None:
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


# ─── ClientTransaction ────────────────────────────────────────────

class _FakeResp:
    def __init__(self, text: str):
        self.text = text


def _init_ct() -> None:
    global _ct_obj, _ct_info
    if not (_CTClass and _USE_CURL):
        _ct_info = f"no_CT({_twikit_diag},curl={_USE_CURL})"
        return
    # twikit 2.3.x: ClientTransaction() takes no args (fetches homepage internally)
    # twikit 2.0-2.2.x: ClientTransaction(response) takes a response object
    for attempt in ("noarg", "resp"):
        try:
            if attempt == "noarg":
                ct = _CTClass()
            else:
                r = curl_req.get(
                    "https://x.com/",
                    headers={"Accept": "text/html,*/*",
                             "Accept-Language": "en-US,en;q=0.9",
                             "Cache-Control": "no-cache"},
                    impersonate="chrome120", timeout=20,
                )
                ct = _CTClass(_FakeResp(r.text))
            # Verify it can generate an ID
            ct.generate_transaction_id("GET", "/i/api/graphql/test/SearchTimeline")
            _ct_obj = ct
            _ct_info = f"CT_OK_{attempt}"
            return
        except Exception as e:
            _ct_info = f"CT_err_{attempt}:{str(e)[:50]}"


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


# ─── twikit.Client high-level search (primary) ───────────────────

async def _search_via_twikit_client(keyword: str, count: int) -> list[dict] | None:
    """
    Use twikit.Client high-level API.
    twikit handles x-client-transaction-id internally (using curl_cffi).
    """
    global _twikit_diag
    try:
        import twikit
        client = twikit.Client("en-US")

        # Inject auth cookies — try multiple methods
        cookies_set = False
        if hasattr(client, "set_cookies"):
            client.set_cookies({"auth_token": _auth_token, "ct0": _ct0})
            cookies_set = True
        elif hasattr(client, "http") and hasattr(client.http, "cookies"):
            client.http.cookies.update({"auth_token": _auth_token, "ct0": _ct0})
            cookies_set = True
        elif hasattr(client, "_session") and hasattr(client._session, "cookies"):
            client._session.cookies.update({"auth_token": _auth_token, "ct0": _ct0})
            cookies_set = True

        if not cookies_set:
            _twikit_diag += ",no_cookie_method"
            return None

        results = await client.search_tweet(keyword, "Latest", count=count)
        tweets: list[dict] = []
        for tweet in results:
            try:
                tweets.append({
                    "id": str(tweet.id),
                    "text": tweet.text or "",
                    "user": tweet.user.screen_name if tweet.user else "unknown",
                    "created_at": str(tweet.created_at or ""),
                    "likes": tweet.favorite_count or 0,
                    "retweets": tweet.retweet_count or 0,
                })
            except Exception:
                pass
        _twikit_diag += f",found={len(tweets)}"
        return tweets

    except ImportError:
        _twikit_diag = "not_installed"
        return None
    except Exception as e:
        err = _redact(str(e))[:80]
        _twikit_diag += f",tw_err:{err}"
        return None


# ─── initialize & warm ───────────────────────────────────────────

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
    _discover_twikit()
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


def debug_info() -> dict:
    return {
        "curl_cffi": _USE_CURL,
        "twikit_diag": _twikit_diag,
        "ct_info": _ct_info,
        "ct_class_found": _CTClass is not None,
        "guest_token_ok": bool(_guest_token),
        "live_qid": (_live_qid[:12] + "...") if _live_qid else None,
    }


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


# ─── manual GraphQL fallback ──────────────────────────────────────

_BASES = [
    "https://x.com/i/api/graphql",
    "https://twitter.com/i/api/graphql",
]


def _try(qid: str, base: str, headers: dict, cookies: dict,
         variables: str) -> list[dict] | str:
    url = f"{base}/{qid}/SearchTimeline"
    short = url.replace("https://", "").replace("twitter.com", "tw.com")[:50]
    ck = {"impersonate": "chrome120"} if _USE_CURL else {}
    params = {"variables": variables, "features": _FEATURES, "fieldToggles": _FIELD_TOGGLES}
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


def _search_manual(keyword: str, count: int) -> list[dict]:
    global _live_qid, _guest_token

    qids: list[str] = []
    if _live_qid:
        qids.append(_live_qid)
    for q in _FALLBACK_QIDS:
        if q not in qids:
            qids.append(q)

    if not _guest_token:
        gt = _activate_guest_token()
        if gt:
            _guest_token = gt

    errors: list[str] = []
    all_404 = True
    cookies = {"auth_token": _auth_token, "ct0": _ct0}
    variables = json.dumps({
        "rawQuery": keyword,
        "count": count,
        "querySource": "typed_query",
        "product": "Latest",
    }, separators=(",", ":"))

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
        for base in _BASES:
            res = _try(qid, base, headers, cookies, variables)
            if isinstance(res, list):
                return res
            errors.append(res)
            if "404" not in res:
                all_404 = False

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
        f"Twitter 검색 실패 (curl={'on' if _USE_CURL else 'off'},"
        f"CT={_ct_info},gt={'on' if _guest_token else 'off'},"
        f"twikit={_twikit_diag}): " + " / ".join(errors)
    )


# ─── public API ───────────────────────────────────────────────────

async def search_tweets(keyword: str, count: int = 30) -> list[dict]:
    if not is_ready():
        raise RuntimeError("Twitter 서비스가 설정되지 않았습니다.")
    count = min(count, MAX_COUNT)

    # Primary: twikit.Client (handles transaction ID internally)
    result = await _search_via_twikit_client(keyword, count)
    if result is not None:
        return result

    # Fallback: manual GraphQL
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, lambda: _search_manual(keyword, count))
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(_redact(str(e)))
