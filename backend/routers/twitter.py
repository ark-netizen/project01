import time
from fastapi import APIRouter, HTTPException, Query
from services.twitter_crawler import is_ready, search_tweets, relogin_required
from services.sentiment import analyze_batch, summarize
from services.keywords import extract_keywords

router = APIRouter(prefix="/api/twitter", tags=["twitter"])

_last_search: float = 0
COOLDOWN = 10  # 초


@router.get("/status")
def twitter_status():
    from services.twitter_crawler import relogin_required, _init_error
    return {"ready": is_ready(), "needs_relogin": relogin_required(), "init_error": _init_error}


@router.get("/search")
async def twitter_search(
    keyword: str = Query(..., min_length=1, max_length=100),
    count: int = Query(default=30, ge=10, le=50),
    since: str = Query(default=None),
    until: str = Query(default=None),
):
    global _last_search

    if not is_ready():
        raise HTTPException(status_code=503, detail="Twitter 서비스가 설정되지 않았습니다.")

    # 서버 측 쿨다운
    elapsed = time.time() - _last_search
    if elapsed < COOLDOWN:
        remaining = int(COOLDOWN - elapsed) + 1
        raise HTTPException(status_code=429, detail=f"{remaining}초 후 다시 시도해주세요.")
    _last_search = time.time()

    query = keyword
    if since:
        query += f" since:{since}"
    if until:
        query += f" until:{until}"

    try:
        tweets = await search_tweets(query, count=count)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not tweets:
        return {"keyword": keyword, "items": [], "summary": summarize([], []), "keywords": []}

    texts = [t["text"] for t in tweets]
    sentiments = analyze_batch(texts)
    items = [{**tweet, "sentiment": s} for tweet, s in zip(tweets, sentiments)]
    errors = [s for s in sentiments if s.get("error")]

    return {
        "keyword": keyword,
        "items": items,
        "summary": summarize(sentiments, tweets),
        "keywords": extract_keywords(texts),
        "sentiment_error": errors[0]["error"] if errors and len(errors) == len(sentiments) else None,
    }
