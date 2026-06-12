import os
import base64
import asyncio

import twikit

_client: twikit.Client | None = None
_COOKIES_PATH = "/tmp/tw_cookies.json"


async def initialize() -> None:
    global _client
    raw = os.getenv("TWITTER_COOKIES", "").strip()
    if not raw:
        return
    try:
        try:
            data = base64.b64decode(raw).decode()
        except Exception:
            data = raw
        with open(_COOKIES_PATH, "w", encoding="utf-8") as f:
            f.write(data)
        client = twikit.Client("ko-KR")
        client.load_cookies(_COOKIES_PATH)
        _client = client
    except Exception:
        _client = None


def is_ready() -> bool:
    return _client is not None


async def search_tweets(keyword: str, count: int = 30) -> list[dict]:
    if not is_ready():
        raise RuntimeError("Twitter 쿠키가 설정되지 않았습니다.")
    count = min(count, 50)
    try:
        results = await _client.search_tweet(keyword, "Latest", count=count)
    except Exception as e:
        msg = str(e).lower()
        if any(k in msg for k in ("unauthorized", "401", "login", "cookie", "session")):
            raise RuntimeError("Twitter 쿠키가 만료됐습니다. 로컬에서 재로그인 후 쿠키를 갱신해주세요.")
        raise RuntimeError(f"Twitter 검색 오류: {str(e)[:120]}")

    tweets = []
    for t in results:
        tweets.append({
            "id": str(t.id),
            "text": t.text or "",
            "user": t.user.screen_name if t.user else "unknown",
            "created_at": str(t.created_at or ""),
            "likes": t.favorite_count or 0,
            "retweets": t.retweet_count or 0,
        })
    return tweets
