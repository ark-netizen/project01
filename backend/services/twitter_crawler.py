import os
from twikit import Client

_client: Client | None = None

MAX_COUNT = 50  # 절대 상한


def _redact(msg: str) -> str:
    """에러 메시지에서 인증 토큰 제거"""
    for key in ("TWITTER_AUTH_TOKEN", "TWITTER_CT0"):
        val = os.getenv(key, "")
        if val and val in msg:
            msg = msg.replace(val, "[REDACTED]")
    return msg


async def initialize() -> None:
    """서버 시작 시 Render 환경변수로 자동 초기화"""
    global _client
    auth_token = os.getenv("TWITTER_AUTH_TOKEN", "").strip()
    ct0 = os.getenv("TWITTER_CT0", "").strip()
    if not auth_token or not ct0:
        return  # 환경변수 미설정 시 조용히 비활성화
    try:
        client = Client(language="ko-KR")
        client.set_cookies({"auth_token": auth_token, "ct0": ct0})
        _client = client
    except Exception:
        pass  # 초기화 실패도 로그에 남기지 않음


def is_ready() -> bool:
    return _client is not None


async def search_tweets(keyword: str, count: int = 30) -> list[dict]:
    if _client is None:
        raise RuntimeError("Twitter 서비스가 설정되지 않았습니다.")

    count = min(count, MAX_COUNT)

    try:
        results = await _client.search_tweet(keyword, product="Top", count=count)
    except Exception as e:
        raise RuntimeError(_redact(str(e)))

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
