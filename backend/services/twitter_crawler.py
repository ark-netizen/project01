import os
import asyncio
import requests as req

_auth_token: str = ""
_ct0: str = ""
MAX_COUNT = 50

_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

_ENDPOINTS = [
    "https://x.com/i/api/1.1/search/tweets.json",
    "https://twitter.com/i/api/1.1/search/tweets.json",
    "https://x.com/i/api/2/search/adaptive.json",
    "https://twitter.com/i/api/2/search/adaptive.json",
]


def _redact(msg: str) -> str:
    for val in (_auth_token, _ct0):
        if val and val in msg:
            msg = msg.replace(val, "[REDACTED]")
    return msg


async def initialize() -> None:
    global _auth_token, _ct0
    _auth_token = os.getenv("TWITTER_AUTH_TOKEN", "").strip()
    _ct0 = os.getenv("TWITTER_CT0", "").strip()


def is_ready() -> bool:
    return bool(_auth_token and _ct0)


def _parse_response(data: dict) -> list[dict] | None:
    if "errors" in data and data["errors"]:
        err = data["errors"][0]
        raise RuntimeError(f"Twitter API 오류({err.get('code','?')}): {err.get('message','unknown')}")

    if "statuses" in data:
        tweets = []
        for tw in data["statuses"]:
            user = tw.get("user", {})
            tweets.append({
                "id": str(tw.get("id_str") or tw.get("id", "")),
                "text": tw.get("full_text") or tw.get("text", ""),
                "user": user.get("screen_name", "unknown"),
                "created_at": tw.get("created_at", ""),
                "likes": tw.get("favorite_count", 0),
                "retweets": tw.get("retweet_count", 0),
            })
        return tweets

    if "globalObjects" in data:
        tweet_objs = data["globalObjects"].get("tweets", {})
        user_objs = data["globalObjects"].get("users", {})
        tweets = []
        for tid, tw in tweet_objs.items():
            uid = str(tw.get("user_id_str", ""))
            user = user_objs.get(uid, {})
            tweets.append({
                "id": tid,
                "text": tw.get("full_text") or tw.get("text", ""),
                "user": user.get("screen_name", "unknown"),
                "created_at": tw.get("created_at", ""),
                "likes": tw.get("favorite_count", 0),
                "retweets": tw.get("retweet_count", 0),
            })
        return tweets

    return None


def _search_sync(keyword: str, count: int) -> list[dict]:
    base_headers = {
        "Authorization": f"Bearer {_BEARER}",
        "x-csrf-token": _ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-client-language": "ko",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://x.com/search",
        "Origin": "https://x.com",
    }
    cookies = {
        "auth_token": _auth_token,
        "ct0": _ct0,
    }
    params = {
        "q": keyword,
        "count": count,
        "tweet_mode": "extended",
        "include_entities": "true",
        "result_type": "recent",
        "query_source": "typed_query",
        "spelling_corrections": "1",
    }

    errors = []
    for url in _ENDPOINTS:
        try:
            r = req.get(url, headers=base_headers, cookies=cookies,
                        params=params, timeout=15, allow_redirects=True)

            if r.status_code in (401, 403):
                errors.append(f"[{url.split('/')[2]}] 인증오류({r.status_code})")
                continue
            if r.status_code == 429:
                raise RuntimeError("Twitter 요청 한도 초과: 잠시 후 다시 시도해주세요.")
            if not r.content or not r.content.strip():
                errors.append(f"[{url.split('/')[2]}] 빈응답")
                continue
            try:
                data = r.json()
            except ValueError:
                errors.append(f"[{url.split('/')[2]}] JSON오류({r.status_code}): {r.text[:80]}")
                continue
            try:
                tweets = _parse_response(data)
            except RuntimeError as e:
                errors.append(f"[{url.split('/')[2]}] {e}")
                continue
            if tweets is not None:
                return tweets
            errors.append(f"[{url.split('/')[2]}] 알수없는형식:{list(data.keys())[:3]}")
        except RuntimeError:
            raise
        except Exception as e:
            errors.append(f"[{url.split('/')[2]}] 예외:{_redact(str(e))[:60]}")

    raise RuntimeError("Twitter 검색 실패: " + " / ".join(errors))


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
