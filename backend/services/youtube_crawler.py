import re
from youtube_comment_downloader import YoutubeCommentDownloader, SORT_BY_RECENT
from youtubesearchpython import VideosSearch


def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def _fetch_comments_by_id(video_id: str, max_per_video: int) -> list[dict]:
    downloader = YoutubeCommentDownloader()
    comments = []
    try:
        for comment in downloader.get_comments_from_url(
            f"https://www.youtube.com/watch?v={video_id}",
            sort_by=SORT_BY_RECENT,
        ):
            comments.append({
                "id": comment.get("cid", ""),
                "text": comment.get("text", ""),
                "author": comment.get("author", ""),
                "votes": comment.get("votes", 0),
                "time": comment.get("time", ""),
                "video_id": video_id,
            })
            if len(comments) >= max_per_video:
                break
    except Exception:
        pass
    return comments


def fetch_comments(url: str, max_count: int = 100) -> list[dict]:
    """URL 하나에서 댓글 수집"""
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"유효하지 않은 YouTube URL: {url}")
    return _fetch_comments_by_id(video_id, max_count)


def fetch_comments_by_keyword(keyword: str, max_videos: int = 10, max_per_video: int = 30) -> tuple[list[dict], list[dict]]:
    """키워드로 상위 영상 검색 후 댓글 수집. (댓글목록, 영상목록) 반환"""
    search = VideosSearch(keyword, limit=max_videos)
    result = search.result()
    videos = result.get("result", [])

    video_info = []
    all_comments = []

    for video in videos:
        vid_id = video.get("id", "")
        if not vid_id:
            continue

        info = {
            "id": vid_id,
            "title": video.get("title", ""),
            "channel": video.get("channel", {}).get("name", ""),
            "views": video.get("viewCount", {}).get("text", ""),
            "url": f"https://www.youtube.com/watch?v={vid_id}",
        }
        video_info.append(info)

        comments = _fetch_comments_by_id(vid_id, max_per_video)
        # 어느 영상 댓글인지 표시
        for c in comments:
            c["video_title"] = info["title"]
        all_comments.extend(comments)

    return all_comments, video_info
