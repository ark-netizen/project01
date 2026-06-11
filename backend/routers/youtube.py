import asyncio
import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.youtube_crawler import fetch_comments, fetch_comments_by_keyword, _fetch_comments_by_id
from services.sentiment import analyze_batch, summarize
from services.keywords import extract_keywords
import dateparser
from datetime import datetime, timezone

router = APIRouter(prefix="/api/youtube", tags=["youtube"])


class YoutubeRequest(BaseModel):
    url: str
    max_count: int = 100
    since: str | None = None
    until: str | None = None


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _filter_by_date(comments, since_dt, until_dt):
    if not since_dt and not until_dt:
        return comments
    filtered = []
    for c in comments:
        time_str = c.get("time", "")
        if not time_str:
            filtered.append(c)
            continue
        try:
            dt = dateparser.parse(time_str, settings={"RETURN_AS_TIMEZONE_AWARE": True})
        except Exception:
            dt = None
        if dt is None:
            filtered.append(c)
            continue
        if since_dt and dt < since_dt:
            continue
        if until_dt and dt > until_dt:
            continue
        filtered.append(c)
    return filtered


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/stream")
async def youtube_keyword_stream(
    keyword: str = Query(...),
    max_videos: int = Query(default=10),
    max_per_video: int = Query(default=30),
    since: str = Query(default=None),
    until: str = Query(default=None),
):
    since_dt = _parse_date(since)
    until_dt = _parse_date(until)

    async def generate():
        loop = asyncio.get_event_loop()

        # 1단계: 영상 검색
        yield _sse({"step": "search", "msg": f"'{keyword}' 관련 영상 검색 중..."})
        try:
            from youtubesearchpython import VideosSearch
            result = await loop.run_in_executor(
                None, lambda: VideosSearch(keyword, limit=max_videos).result()
            )
            videos = result.get("result", [])
        except Exception as e:
            yield _sse({"step": "error", "msg": f"영상 검색 실패: {e}"})
            return

        video_info = [
            {
                "id": v.get("id", ""),
                "title": v.get("title", ""),
                "channel": v.get("channel", {}).get("name", ""),
                "url": f"https://www.youtube.com/watch?v={v.get('id','')}",
            }
            for v in videos if v.get("id")
        ]
        yield _sse({"step": "found", "msg": f"{len(video_info)}개 영상 발견", "videos": video_info})

        # 2단계: 댓글 수집
        all_comments = []
        for i, v in enumerate(video_info):
            yield _sse({"step": "crawl", "msg": f"댓글 수집 중 ({i+1}/{len(video_info)})", "current": i + 1, "total": len(video_info)})
            comments = await loop.run_in_executor(
                None, lambda vid=v: _fetch_comments_by_id(vid["id"], max_per_video)
            )
            for c in comments:
                c["video_title"] = v["title"]
            all_comments.extend(comments)
            yield _sse({"step": "ping"})  # keepalive

        all_comments = _filter_by_date(all_comments, since_dt, until_dt)

        if not all_comments:
            yield _sse({"step": "done", "result": {"items": [], "summary": summarize([], []), "keywords": [], "videos": video_info}})
            return

        # 3단계: 감성 분석
        yield _sse({"step": "analyze", "msg": f"총 {len(all_comments)}개 댓글 감성 분석 중..."})
        texts = [c["text"] for c in all_comments]
        sentiments = await loop.run_in_executor(None, analyze_batch, texts)

        # 4단계: 키워드 추출
        yield _sse({"step": "keywords", "msg": "키워드 추출 중..."})
        keywords_data = extract_keywords(texts)

        items = [{**c, "sentiment": s} for c, s in zip(all_comments, sentiments)]
        errors = [s for s in sentiments if s.get("error")]
        result_data = {
            "items": items,
            "summary": summarize(sentiments, all_comments),
            "keywords": keywords_data,
            "videos": video_info,
            "sentiment_error": errors[0]["error"] if errors and len(errors) == len(sentiments) else None,
        }
        yield _sse({"step": "done", "result": result_data})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/analyze")
def youtube_analyze(body: YoutubeRequest):
    """URL 단일 분석 (URL 모드)"""
    since_dt = _parse_date(body.since)
    until_dt = _parse_date(body.until)

    try:
        comments = fetch_comments(body.url, max_count=body.max_count)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube 크롤링 실패: {e}")

    comments = _filter_by_date(comments, since_dt, until_dt)
    if not comments:
        return {"items": [], "summary": summarize([], []), "keywords": [], "videos": []}

    texts = [c["text"] for c in comments]
    sentiments = analyze_batch(texts)
    keywords_data = extract_keywords(texts)
    items = [{**c, "sentiment": s} for c, s in zip(comments, sentiments)]

    errors = [s for s in sentiments if s.get("error")]
    return {
        "items": items,
        "summary": summarize(sentiments, comments),
        "keywords": keywords_data,
        "videos": [],
        "sentiment_error": errors[0]["error"] if errors and len(errors) == len(sentiments) else None,
    }
