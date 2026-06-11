from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.youtube_crawler import fetch_comments, fetch_comments_by_keyword
from services.sentiment import analyze_batch, summarize
from services.keywords import extract_keywords
import dateparser
from datetime import datetime, timezone

router = APIRouter(prefix="/api/youtube", tags=["youtube"])


class YoutubeRequest(BaseModel):
    mode: str = "url"        # "url" | "keyword"
    url: str | None = None
    keyword: str | None = None
    max_count: int = 100
    max_videos: int = 10
    max_per_video: int = 30
    since: str | None = None
    until: str | None = None


def _parse_date(s: str | None) -> datetime | None:
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
        return dateparser.parse(time_str, settings={"RETURN_AS_TIMEZONE_AWARE": True})
    except Exception:
        return None


def _filter_by_date(comments, since_dt, until_dt):
    if not since_dt and not until_dt:
        return comments
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
    return filtered


@router.post("/analyze")
def youtube_analyze(body: YoutubeRequest):
    since_dt = _parse_date(body.since)
    until_dt = _parse_date(body.until)
    video_info = []

    if body.mode == "keyword":
        if not body.keyword:
            raise HTTPException(status_code=400, detail="keyword를 입력해주세요.")
        try:
            comments, video_info = fetch_comments_by_keyword(
                body.keyword,
                max_videos=body.max_videos,
                max_per_video=body.max_per_video,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"YouTube 검색 실패: {e}")
    else:
        if not body.url:
            raise HTTPException(status_code=400, detail="url을 입력해주세요.")
        try:
            comments = fetch_comments(body.url, max_count=body.max_count)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"YouTube 크롤링 실패: {e}")

    comments = _filter_by_date(comments, since_dt, until_dt)

    if not comments:
        return {"mode": body.mode, "items": [], "summary": summarize([], []), "keywords": [], "videos": video_info}

    texts = [c["text"] for c in comments]
    sentiments = analyze_batch(texts)
    keywords = extract_keywords(texts)

    items = [{**c, "sentiment": s} for c, s in zip(comments, sentiments)]

    return {
        "mode": body.mode,
        "items": items,
        "summary": summarize(sentiments, comments),
        "keywords": keywords,
        "videos": video_info,
    }
