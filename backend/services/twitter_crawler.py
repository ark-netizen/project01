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

# 시도할 엔드포인트 목록 (순서대로 시도)
_ENDPOINTS = [
    ("https://twitter.com/i/api/1.1/search/tweets.json", {
        "tweet_mode": "extended",
        "include_entities": "true",
        "result_type": "recent",
    }),
    ("https://twitter.com/i/api/1.1/search/tweets.json", {
        "tweet_mode": "extended",
        "include_entities": "true",
        "result_type": "mixed",
    }),
    ("https://twitter.com/i/api/2/search/adaptive.json", {
        "tweet_mode": "extended",
        "include_entities": "true",
        "query_source": "typed_query",
    }),
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
    # 포맷 1: 1.1 statuses 배열
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

    # 포맷 2: adaptive.json globalObjects
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
    headers = {
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
        "Referer": "https://twitter.com/search",
        "Origin": "https://twitter.com",
    }
    cookies = {"auth_token": _auth_token, "ct0": _ct0}
    last_error = "알 수 없는 오류"

    for url, extra_params in _ENDPOINTS:
        params = {"q": keyword, "count": count, **extra_params}
        try:
            r = req.get(url, headers=headers, cookies=cookies, params=params, timeout=15)
            if r.status_code in (401, 403):
                raise RuntimeError("Twitter 인증 오류: 쿠키가 만료됐거나 잘못됐습니다.")
            if r.status_code == 429:
                raise RuntimeError("Twitter 요청 한도 초과: 잠시 후 다시 시도해주세요.")
            if not r.content:
                last_error = f"{url} 응답 비어있음"
                continue
            try:
                data = r.json()
            except ValueError:
                last_error = f"{url} JSON 파싱 실패: {r.text[:100]}"
                continue
            tweets = _parse_response(data)
            if tweets is not None:
                return tweets
            last_error = f"{url} 알 수 없는 응답 형식: {list(data.keys())}"
        except RuntimeError:
            raise
        except Exception as e:
            last_error = _redact(str(e))

    raise RuntimeError(f"Twitter 검색 실패: {last_error}")


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
