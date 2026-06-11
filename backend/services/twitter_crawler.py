import os
import re
import json
import math
import time
import random
import hashlib
import uuid
import base64
import secrets
import asyncio
import threading
import importlib
import pkgutil
from functools import reduce
from typing import List, Union

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

# x-client-transaction-id 알고리즘 상수 (twikit 2.3.3에서 확인)
_CT_KEYWORD = "obfiowerehiring"
_CT_EXTRA = 3

_live_qid: str | None = None
_guest_token: str | None = None
_ct_state: dict = {}   # {key, key_bytes, soup, row_idx, key_indices}
_ct_info: str = "not_init"
_qid_lock = threading.Lock()
_CLIENT_UUID = str(uuid.uuid4())


def _redact(msg: str) -> str:
    for val in (_auth_token, _ct0):
        if val and val in msg:
            msg = msg.replace(val, "[REDACTED]")
    return msg


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


# ─── x-client-transaction-id (native implementation) ─────────────

class _Cubic:
    """Cubic bezier helper (port of twikit's Cubic class)."""
    def __init__(self, curves: list):
        self.curves = curves

    def get_value(self, t: float) -> float:
        start = 0.0
        for i, curve in enumerate(self.curves):
            if i == len(self.curves) - 1 or curve >= t:
                if i == 0:
                    return 0.0
                p0 = self.curves[i - 1]
                p1 = curve
                seg = (t - p0) / (p1 - p0) if p1 != p0 else 0.0
                return seg
        return 1.0


def _interpolate(a: list, b: list, t: float) -> list:
    return [a[i] + (b[i] - a[i]) * t for i in range(len(a))]


def _convert_rotation_to_matrix(deg: float) -> list:
    rad = math.radians(deg)
    c, s = math.cos(rad), math.sin(rad)
    return [c, -s, s, c]


def _float_to_hex(f: float) -> str:
    if f == 0:
        return "0"
    s = f"{f:.10f}".rstrip("0").rstrip(".")
    if "." in s:
        int_part, dec_part = s.split(".")
        return f"{int_part}.{dec_part}" if int_part else f".{dec_part}"
    return s


def _is_odd(n: int) -> int:
    return n % 2


def _solve(value: float, min_val: float, max_val: float, rounding: bool) -> float:
    result = value * (max_val - min_val) / 255 + min_val
    return math.floor(result) if rounding else round(result, 2)


def _animate(frames: list, target_time: float) -> str:
    from_color = [float(x) for x in [*frames[:3], 1]]
    to_color   = [float(x) for x in [*frames[3:6], 1]]
    from_rot   = [0.0]
    to_rot     = [_solve(float(frames[6]), 60.0, 360.0, True)]
    rem = frames[7:]
    curves = [_solve(float(v), _is_odd(i), 1.0, False) for i, v in enumerate(rem)]
    cubic = _Cubic(curves)
    val = cubic.get_value(target_time)
    color = [max(v, 0) for v in _interpolate(from_color, to_color, val)]
    rotation = _interpolate(from_rot, to_rot, val)
    matrix = _convert_rotation_to_matrix(rotation[0])
    arr = [format(round(v), 'x') for v in color[:-1]]
    for v in matrix:
        rv = abs(round(v, 2))
        hx = _float_to_hex(rv)
        arr.append(f"0{hx}".lower() if hx.startswith(".") else hx if hx else "0")
    arr.extend(["0", "0"])
    return re.sub(r"[.-]", "", "".join(arr))


def _get_key_byte_indices(html: str) -> tuple[int, list]:
    """Try to get row_index & key_indices from ondemand.s JS; fallback to known values."""
    if not _USE_CURL:
        return 2, [12, 14, 7]

    # 1. Search HTML for ondemand.s hash
    hash_val = None
    for pat in (
        r'"ondemand\.s"\s*:\s*"([a-f0-9]+)"',
        r'ondemand\.s\.([\w]+?)a?\.js',
        r'["\']([\w]{7,10})["\']\s*:\s*"ondemand\.s"',
    ):
        m = re.search(pat, html)
        if m:
            hash_val = m.group(1)
            break

    # 2. If not in HTML, search main JS bundle
    if not hash_val:
        bundle_urls = list(dict.fromkeys(re.findall(
            r'https://abs\.twimg\.com/responsive-web/client-web/main\.[^\s"\'<>]+\.js', html
        )))
        for u in bundle_urls[:2]:
            try:
                jr = curl_req.get(u, impersonate="chrome120", timeout=15)
                txt = jr.text or ""
                for pat in (
                    r'"ondemand\.s"\s*:\s*"([a-f0-9]+)"',
                    r'ondemand\.s\.([\w]+?)a?\.js',
                ):
                    m = re.search(pat, txt)
                    if m:
                        hash_val = m.group(1)
                        break
            except Exception:
                pass
            if hash_val:
                break

    # 3. If hash found, fetch the ondemand.s JS and parse indices
    if hash_val:
        for url in (
            f"https://abs.twimg.com/responsive-web/client-web/ondemand.s.{hash_val}a.js",
            f"https://abs.twimg.com/responsive-web/client-web/ondemand.s.{hash_val}.js",
        ):
            try:
                jr = curl_req.get(url, impersonate="chrome120", timeout=15)
                if jr.status_code == 200 and jr.text:
                    nums = [int(x) for x in re.findall(r'\b(\d{1,3})\b', jr.text)
                            if 0 <= int(x) <= 255]
                    if len(nums) >= 4:
                        return nums[0], nums[1:4]
            except Exception:
                pass

    # 4. Fallback: last known values from twikit source comments
    return 2, [12, 14, 7]


def _generate_transaction_id(method: str, path: str, soup, key_bytes: list,
                              row_idx: int, key_indices: list) -> str:
    total_time = 4096
    frames_list = soup.select("[id^='loading-x-anim']")
    frame = list(list(frames_list[key_bytes[5] % 4].children)[0].children)[1]
    raw_d = frame.get("d", "")[9:]
    arr2d = [[int(x) for x in re.sub(r"[^\d]+", " ", seg).strip().split()]
             for seg in raw_d.split("C")]

    row_index = key_bytes[row_idx] % 16
    frame_time = reduce(lambda a, b: a * b,
                        [key_bytes[idx] % 16 for idx in key_indices])
    frame_row = arr2d[row_index]
    target_time = float(frame_time) / total_time
    animation_key = _animate(frame_row, target_time)

    t_now = math.floor((time.time() * 1000 - 1682924400 * 1000) / 1000)
    t_bytes = [(t_now >> (i * 8)) & 0xFF for i in range(4)]
    h = hashlib.sha256(
        f"{method}!{path}!{t_now}{_CT_KEYWORD}{animation_key}".encode()
    ).digest()
    rand = random.randint(0, 255)
    payload = [*key_bytes, *t_bytes, *list(h)[:16], _CT_EXTRA]
    out = bytearray([rand, *[b ^ rand for b in payload]])
    return base64.b64encode(bytes(out)).decode().rstrip("=")


def _init_ct() -> None:
    global _ct_state, _ct_info
    if not _USE_CURL:
        _ct_info = "no_curl"
        return
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        _ct_info = "no_bs4"
        return
    try:
        r = curl_req.get(
            "https://x.com/",
            headers={"Accept": "text/html,*/*", "Accept-Language": "en-US,en;q=0.9",
                     "Cache-Control": "no-cache"},
            impersonate="chrome120", timeout=20,
        )
        html = r.text or ""
        soup = BeautifulSoup(html, "html.parser")

        meta = soup.select_one("[name='twitter-site-verification']")
        if not meta:
            _ct_info = "CT_err:no_meta_tag"
            return
        key = meta.get("content", "")
        key_bytes = list(base64.b64decode(key.encode()))

        frames = soup.select("[id^='loading-x-anim']")
        if len(frames) < 4:
            _ct_info = f"CT_err:frames={len(frames)}"
            return

        row_idx, key_indices = _get_key_byte_indices(html)

        # Verify the algorithm runs without error
        _generate_transaction_id("GET", "/i/api/graphql/test/SearchTimeline",
                                  soup, key_bytes, row_idx, key_indices)

        _ct_state = {
            "soup": soup,
            "key_bytes": key_bytes,
            "row_idx": row_idx,
            "key_indices": key_indices,
        }
        _ct_info = f"CT_OK(idx={row_idx},{key_indices})"
    except Exception as e:
        _ct_info = f"CT_err:{str(e)[:80]}"


def _txn_id(method: str, path: str) -> str:
    if _ct_state:
        try:
            return _generate_transaction_id(
                method, path,
                _ct_state["soup"],
                _ct_state["key_bytes"],
                _ct_state["row_idx"],
                _ct_state["key_indices"],
            )
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
        "ct_info": _ct_info,
        "ct_ok": bool(_ct_state),
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


# ─── manual GraphQL search ────────────────────────────────────────

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


def _search_sync(keyword: str, count: int) -> list[dict]:
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
        f"Twitter 검색 실패 (CT={_ct_info},gt={'on' if _guest_token else 'off'}): "
        + " / ".join(errors)
    )


# ─── public API ───────────────────────────────────────────────────

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
