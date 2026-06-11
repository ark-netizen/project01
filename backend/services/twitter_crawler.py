import os
from twikit import Client

_client: Client | None = None
MAX_COUNT = 50


def _redact(msg: str) -> str:
    for key in ("TWITTER_AUTH_TOKEN", "TWITTER_CT0"):
        val = os.getenv(key, "")
        if val and val in msg:
            msg = msg.replace(val, "[REDACTED]")
    return msg


def _patch_twikit():
    """Render 서버 IP에서 Twitter JS 파싱 실패(KEY_BYTE) 우회 패치"""
    async def _no_txn(self, *args, **kwargs):
        return ""

    try:
        import twikit.client_transaction as ct

        # __init__을 래핑해서 key 속성을 항상 초기화
        _orig_init = ct.ClientTransaction.__init__
        def _safe_init(self, *args, **kwargs):
            try:
                _orig_init(self, *args, **kwargs)
            except Exception:
                pass
            try:
                self.key = None
            except Exception:
                pass
            try:
                self.key_bytes_indices = []
            except Exception:
                pass

        ct.ClientTransaction.__init__ = _safe_init
        ct.ClientTransaction.get_transaction_id = _no_txn
    except Exception:
        pass

    try:
        from twikit.client.client import Client as TC
        TC._get_client_transaction_id = _no_txn
    except Exception:
        pass


async def initialize() -> None:
    global _client
    auth_token = os.getenv("TWITTER_AUTH_TOKEN", "").strip()
    ct0 = os.getenv("TWITTER_CT0", "").strip()
    if not auth_token or not ct0:
        return
    try:
        _patch_twikit()
        client = Client(language="ko-KR")
        client.set_cookies({"auth_token": auth_token, "ct0": ct0})
        _client = client
    except Exception:
        pass


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
