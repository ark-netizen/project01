import os
import re
import asyncio

try:
    from curl_cffi import requests as curl_req
    _USE_CURL = True
except ImportError:
    import requests as curl_req  # type: ignore[no-redef]
    _USE_CURL = False

_bearer_token: str = ""
MAX_COUNT = 100

_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"


async def initialize() -> None:
    global _bearer_token
    _bearer_token = os.getenv("TWITTER_BEARER_TOKEN", "").strip()


def is_ready() -> bool:
    return bool(_bearer_token)


def _search_sync(keyword: str, count: int) -> list[dict]:
    query = keyword
    start_time = None
    end_time = None

    m = re.search(r'\bsince:(\S+)', query)
    if m:
        start_time = m.group(1) + "T00:00:00Z"
        query = query.replace(m.group(0), "").strip()

    m = re.search(r'\buntil:(\S+)', query)
    if m:
        end_time = m.group(1) + "T00:00:00Z"
        query = query.replace(m.group(0), "").strip()

    params = {
        "query": query,
        "max_results": min(max(count, 10), 100),
        "tweet.fields": "created_at,public_metrics,text",
        "expansions": "author_id",
        "user.fields": "username",
    }
    if start_time:
        params["start_time"] = start_time
    if end_time:
        params["end_time"] = end_time

    headers = {"Authorization": f"Bearer {_bearer_token}"}
    ck = {"impersonate": "chrome120"} if _USE_CURL else {}

    r = curl_req.get(_SEARCH_URL, headers=headers, params=params, timeout=15, **ck)

    if r.status_code == 429:
        raise RuntimeError("Twitter API 요청 한도 초과: 잠시 후 다시 시도해주세요.")
    if r.status_code == 401:
        raise RuntimeError("Twitter Bearer Token이 유효하지 않습니다.")
    if r.status_code == 403:
        raise RuntimeError("Twitter API 접근 권한이 없습니다. 플랜을 확인해주세요.")
    if r.status_code != 200:
        try:
            err = r.json()
            detail = err.get("detail") or err.get("title") or str(err)[:100]
        except Exception:
            detail = r.text[:100]
        raise RuntimeError(f"Twitter API 오류 ({r.status_code}): {detail}")

    data = r.json()
    tweets_raw = data.get("data") or []

    if not tweets_raw:
        return []

    users = {
        u["id"]: u.get("username", "unknown")
        for u in data.get("includes", {}).get("users", [])
    }

    return [
        {
            "id": t["id"],
            "text": t.get("text", ""),
            "user": users.get(t.get("author_id", ""), "unknown"),
            "created_at": t.get("created_at", ""),
            "likes": t.get("public_metrics", {}).get("like_count", 0),
            "retweets": t.get("public_metrics", {}).get("retweet_count", 0),
        }
        for t in tweets_raw
    ]


async def search_tweets(keyword: str, count: int = 30) -> list[dict]:
    if not is_ready():
        raise RuntimeError("Twitter Bearer Token이 설정되지 않았습니다.")
    count = min(count, MAX_COUNT)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _search_sync(keyword, count))
