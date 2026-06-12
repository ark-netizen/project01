import asyncio
import re

try:
    from ntscraper import Nitter
    _scraper = Nitter(log_level=0, skip_instance_check=False)
    _NTSCRAPER_OK = True
except Exception:
    _NTSCRAPER_OK = False

MAX_COUNT = 50


async def initialize() -> None:
    pass


def is_ready() -> bool:
    return _NTSCRAPER_OK


def relogin_required() -> bool:
    return False


def _extract_id(link: str) -> str:
    m = re.search(r'/status/(\d+)', link or "")
    return m.group(1) if m else ""


def _search_sync(keyword: str, count: int) -> list[dict]:
    results = _scraper.get_tweets(keyword, mode="term", number=count)
    tweets_raw = (results or {}).get("tweets") or []

    tweets = []
    for t in tweets_raw:
        text = t.get("text") or ""
        user = (t.get("user") or {}).get("username") or "unknown"
        date = t.get("date") or ""
        likes = t.get("likes") or 0
        retweets = t.get("retweets") or 0
        link = t.get("link") or ""
        tid = _extract_id(link)

        try:
            likes = int(str(likes).replace(",", ""))
        except Exception:
            likes = 0
        try:
            retweets = int(str(retweets).replace(",", ""))
        except Exception:
            retweets = 0

        tweets.append({
            "id": tid,
            "text": text,
            "user": user,
            "created_at": date,
            "likes": likes,
            "retweets": retweets,
        })
    return tweets


async def search_tweets(keyword: str, count: int = 30) -> list[dict]:
    if not is_ready():
        raise RuntimeError("ntscraper 초기화에 실패했습니다.")
    count = min(count, MAX_COUNT)
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, lambda: _search_sync(keyword, count))
    except Exception as e:
        raise RuntimeError(f"Twitter 검색 오류: {str(e)[:120]}")
