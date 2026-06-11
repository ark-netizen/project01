import os
import asyncio
import requests as req

_auth_token: str = ""
_ct0: str = ""
MAX_COUNT = 50

# Twitter 웹 앱 공개 Bearer Token
_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)


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
        "Accept": "*/*",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://twitter.com/search",
    }
    cookies = {"auth_token": _auth_token, "ct0": _ct0}

    r = req.get(
        "https://twitter.com/i/api/2/search/adaptive.json",
        headers=headers,
        cookies=cookies,
        params={
            "q": keyword,
            "count": count,
            "tweet_mode": "extended",
            "include_entities": "true",
            "query_source": "typed_query",
            "spelling_corrections": "1",
        },
        timeout=15,
    )

    if r.status_code == 403:
        raise RuntimeError("Twitter 인증 오류: 쿠키가 만료됐거나 잘못됐습니다.")
    if r.status_code == 429:
        raise RuntimeError("Twitter 요청 한도 초과: 잠시 후 다시 시도해주세요.")
    r.raise_for_status()

    data = r.json()
    tweet_objs = data.get("globalObjects", {}).get("tweets", {})
    user_objs = data.get("globalObjects", {}).get("users", {})

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
