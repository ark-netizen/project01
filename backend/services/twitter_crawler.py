import asyncio
from twikit import Client

_client: Client | None = None
_lock = asyncio.Lock()


async def login(username: str, email: str, password: str) -> None:
    global _client
    async with _lock:
        client = Client(language="ko-KR")
        await client.login(
            auth_info_1=username,
            auth_info_2=email,
            password=password,
        )
        _client = client


def is_logged_in() -> bool:
    return _client is not None


async def logout() -> None:
    global _client
    _client = None


async def search_tweets(keyword: str, count: int = 50) -> list[dict]:
    if _client is None:
        raise RuntimeError("로그인이 필요합니다.")

    results = await _client.search_tweet(keyword, product="Top", count=count)

    tweets = []
    for tweet in results:
        tweets.append({
            "id": tweet.id,
            "text": tweet.text,
            "user": tweet.user.screen_name if tweet.user else "unknown",
            "created_at": str(tweet.created_at) if tweet.created_at else "",
            "likes": tweet.favorite_count or 0,
            "retweets": tweet.retweet_count or 0,
        })
    return tweets
