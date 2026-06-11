from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.youtube_crawler import fetch_comments
from services.sentiment import analyze_batch, summarize
import dateparser
from datetime import datetime, timezone

router = APIRouter(prefix="/api/youtube", tags=["youtube"])


class YoutubeRequest(BaseModel):
    url: str
    max_count: int = 100
    since: str | None = None
    until: str | None = None


def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_comment_time(time_str: str) -> datetime | None:
    if not time_str:
        return None
    try:
        dt = dateparser.parse(time_str, settings={"RETURN_AS_TIMEZONE_AWARE": True})
        return dt
    except Exception:
        return None


@router.post("/analyze")
def youtube_analyze(body: YoutubeRequest):
    try:
        comments = fetch_comments(body.url, max_count=body.max_count)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube 크롤링 실패: {e}")

    # 날짜 필터 적용
    since_dt = _parse_date(body.since)
    until_dt = _parse_date(body.until)

    if since_dt or until_dt:
        filtered = []
        for c in comments:
            dt = _parse_comment_time(c.get("time", ""))
            if dt is None:
                filtered.append(c)
                continue
            if since_dt and dt < since_dt:
                continue
            if until_dt and dt > until_dt:
                continue
            filtered.append(c)
        comments = filtered

    if not comments:
        return {"url": body.url, "items": [], "summary": summarize([], [])}

    texts = [c["text"] for c in comments]
    sentiments = analyze_batch(texts)

    items = [{**comment, "sentiment": sentiment} for comment, sentiment in zip(comments, sentiments)]

    return {
        "url": body.url,
        "items": items,
        "summary": summarize(sentiments, comments),
    }
