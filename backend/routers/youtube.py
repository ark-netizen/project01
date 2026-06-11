import asyncio
import time
import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel
from services.youtube_crawler import fetch_comments, _fetch_comments_by_id
from services.sentiment import analyze_batch, summarize
from services.keywords import extract_keywords
import dateparser
from datetime import datetime, timezone

router = APIRouter(prefix="/api/youtube", tags=["youtube"])

# 인메모리 작업 저장소 (폴링 방식)
_jobs: dict = {}


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


async def _run_keyword_analysis(job_id: str, keyword: str, max_videos: int,
                                 max_per_video: int, since_dt, until_dt):
    def upd(**kw):
        _jobs[job_id].update(kw)

    loop = asyncio.get_event_loop()
    try:
        # 1. 영상 검색
        upd(step="search", msg=f"'{keyword}' 관련 영상 검색 중...")
        from youtubesearchpython import VideosSearch
        search_result = await loop.run_in_executor(
            None, lambda: VideosSearch(keyword, limit=max_videos).result()
        )
        videos = search_result.get("result", [])
        video_info = [
            {
                "id": v.get("id", ""),
                "title": v.get("title", ""),
                "channel": v.get("channel", {}).get("name", ""),
                "url": f"https://www.youtube.com/watch?v={v.get('id','')}",
            }
            for v in videos if v.get("id")
        ]
        upd(step="found", msg=f"{len(video_info)}개 영상 발견", videos=video_info, total=len(video_info))

        # 2. 댓글 수집
        all_comments = []
        for i, v in enumerate(video_info):
            upd(step="crawl", msg=f"댓글 수집 중 ({i+1}/{len(video_info)})", current=i + 1)
            comments = await loop.run_in_executor(
                None, lambda vid=v: _fetch_comments_by_id(vid["id"], max_per_video)
            )
            for c in comments:
                c["video_title"] = v["title"]
            all_comments.extend(comments)

        all_comments = _filter_by_date(all_comments, since_dt, until_dt)

        if not all_comments:
            upd(status="done", result={
                "items": [], "summary": summarize([], []),
                "keywords": [], "videos": video_info,
            })
            return

        # 3. 감성 분석
        upd(step="analyze", msg=f"총 {len(all_comments)}개 댓글 감성 분석 중...")
        texts = [c["text"] for c in all_comments]
        sentiments = await loop.run_in_executor(None, analyze_batch, texts)

        # 4. 키워드 추출
        upd(step="keywords", msg="키워드 추출 중...")
        keywords_data = extract_keywords(texts)

        items = [{**c, "sentiment": s} for c, s in zip(all_comments, sentiments)]
        errors = [s for s in sentiments if s.get("error")]
        upd(
            status="done",
            result={
                "items": items,
                "summary": summarize(sentiments, all_comments),
                "keywords": keywords_data,
                "videos": video_info,
                "sentiment_error": errors[0]["error"] if errors and len(errors) == len(sentiments) else None,
            },
        )
    except Exception as e:
        upd(status="error", error=str(e))


@router.post("/analyze-keyword")
async def start_keyword_analysis(
    background_tasks: BackgroundTasks,
    keyword: str = Query(...),
    max_videos: int = Query(default=10),
    max_per_video: int = Query(default=30),
    since: str = Query(default=None),
    until: str = Query(default=None),
):
    # 10분 지난 작업 정리
    now = time.time()
    for k in [k for k, v in list(_jobs.items()) if now - v.get("created_at", 0) > 600]:
        del _jobs[k]

    job_id = str(uuid.uuid4())
    since_dt = _parse_date(since)
    until_dt = _parse_date(until)
    _jobs[job_id] = {
        "status": "running",
        "step": "search",
        "msg": "시작 중...",
        "current": 0,
        "total": 0,
        "videos": [],
        "result": None,
        "error": None,
        "created_at": now,
    }
    background_tasks.add_task(
        _run_keyword_analysis, job_id, keyword, max_videos, max_per_video, since_dt, until_dt
    )
    return {"job_id": job_id}


@router.get("/job/{job_id}")
def get_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    return job


@router.post("/analyze")
def youtube_analyze(body: YoutubeRequest):
    """URL 단일 분석"""
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
