from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.youtube_crawler import fetch_comments
from services.sentiment import analyze_batch, summarize

router = APIRouter(prefix="/api/youtube", tags=["youtube"])


class YoutubeRequest(BaseModel):
    url: str
    max_count: int = 100


@router.post("/analyze")
def youtube_analyze(body: YoutubeRequest):
    try:
        comments = fetch_comments(body.url, max_count=body.max_count)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube 크롤링 실패: {e}")

    if not comments:
        return {"url": body.url, "items": [], "summary": summarize([])}

    texts = [c["text"] for c in comments]
    sentiments = analyze_batch(texts)

    items = []
    for comment, sentiment in zip(comments, sentiments):
        items.append({**comment, "sentiment": sentiment})

    return {
        "url": body.url,
        "items": items,
        "summary": summarize(sentiments, comments),
    }
