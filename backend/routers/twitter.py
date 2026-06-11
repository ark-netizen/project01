from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from services.twitter_crawler import login, logout, is_logged_in, search_tweets
from services.sentiment import analyze_batch, summarize
from services.keywords import extract_keywords

router = APIRouter(prefix="/api/twitter", tags=["twitter"])


class LoginRequest(BaseModel):
    username: str
    email: str
    password: str


@router.post("/login")
async def twitter_login(body: LoginRequest):
    try:
        await login(body.username, body.email, body.password)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"로그인 실패: {e}")
    return {"status": "ok"}


@router.post("/logout")
async def twitter_logout():
    await logout()
    return {"status": "ok"}


@router.get("/status")
def twitter_status():
    return {"logged_in": is_logged_in()}


@router.get("/search")
async def twitter_search(
    keyword: str = Query(..., min_length=1, max_length=100),
    count: int = Query(default=50, ge=10, le=100),
    since: str = Query(default=None, description="YYYY-MM-DD"),
    until: str = Query(default=None, description="YYYY-MM-DD"),
):
    if not is_logged_in():
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    # Twitter 검색 문법으로 날짜 범위 추가
    query = keyword
    if since:
        query += f" since:{since}"
    if until:
        query += f" until:{until}"

    try:
        tweets = await search_tweets(query, count=count)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"크롤링 실패: {e}")

    if not tweets:
        return {"keyword": keyword, "items": [], "summary": summarize([], [])}

    texts = [t["text"] for t in tweets]
    sentiments = analyze_batch(texts)

    items = [{**tweet, "sentiment": sentiment} for tweet, sentiment in zip(tweets, sentiments)]

    return {
        "keyword": keyword,
        "items": items,
        "summary": summarize(sentiments, tweets),
        "keywords": extract_keywords([t["text"] for t in tweets]),
    }
