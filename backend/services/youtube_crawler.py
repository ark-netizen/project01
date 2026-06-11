from youtube_comment_downloader import YoutubeCommentDownloader, SORT_BY_RECENT
import re


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


def fetch_comments(url: str, max_count: int = 100) -> list[dict]:
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"유효하지 않은 YouTube URL: {url}")

    downloader = YoutubeCommentDownloader()
    comments = []

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
        })
        if len(comments) >= max_count:
            break

    return comments
