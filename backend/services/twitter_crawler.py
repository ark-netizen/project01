import os
import json
import asyncio
import requests as req

_auth_token: str = ""
_ct0: str = ""
MAX_COUNT = 50

_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

# Twitter GraphQL SearchTimeline query IDs (try multiple — changes periodically)
_GRAPHQL_QIDS = [
    "nK1dw4oV3k4w5TdtcAdSww",
    "gkjsKepM6gl_HmFWoWKfgg",
    "7jMcZ7NW_rL6MHT9WnRFkg",
]

_FEATURES = json.dumps({
    "rweb_lists_timeline_redesign_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": False,
    "tweet_awards_web_tipping_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_media_download_video_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
}, separators=(',', ':'))

_FIELD_TOGGLES = json.dumps({"withArticleRichContentState": False}, separators=(',', ':'))


def _redact(msg: str) -> str:
    for val in (_auth_token, _ct0):
        if val and val in msg:
            msg = msg.replace(val, "[REDACTED]")
    return msg


async def initialize() -> None:
    global _auth_token, _ct0
    _auth_token = os.getenv("TWITTER_AUTH_TOKEN", "").strip()
    _ct0 = os.getenv("TWITTER_CT0", "").strip()


def is_ready() -> bool:
    return bool(_auth_token and _ct0)


def _parse_graphql(data: dict) -> list[dict] | None:
    try:
        instructions = (
            data["data"]["search_by_raw_query"]["search_timeline"]["timeline"]["instructions"]
        )
    except (KeyError, TypeError):
        return None

    tweets = []
    for inst in instructions:
        t = inst.get("type", "")
        if t == "TimelineAddEntries":
            raw_entries = inst.get("entries", [])
        elif t == "TimelineAddToModule":
            raw_entries = inst.get("moduleItems", [])
        else:
            continue

        for entry in raw_entries:
            # content lives under "content" (TimelineAddEntries) or "item" (TimelineAddToModule)
            content = entry.get("content") or entry.get("item") or {}
            item_content = content.get("itemContent", {})

            if item_content.get("itemType") != "TimelineTweet":
                continue

            result = item_content.get("tweet_results", {}).get("result", {})
            if not result:
                continue

            # TweetWithVisibilityResults wraps the actual tweet
            if result.get("__typename") == "TweetWithVisibilityResults":
                result = result.get("tweet", result)

            legacy = result.get("legacy", {})
            user_legacy = (
                result.get("core", {})
                      .get("user_results", {})
                      .get("result", {})
                      .get("legacy", {})
            )
            if not legacy:
                continue

            tweets.append({
                "id": legacy.get("id_str", ""),
                "text": legacy.get("full_text") or legacy.get("text", ""),
                "user": user_legacy.get("screen_name", "unknown"),
                "created_at": legacy.get("created_at", ""),
                "likes": legacy.get("favorite_count", 0),
                "retweets": legacy.get("retweet_count", 0),
            })

    return tweets if tweets else None


def _search_sync(keyword: str, count: int) -> list[dict]:
    headers = {
        "Authorization": f"Bearer {_BEARER}",
        "x-csrf-token": _ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-client-language": "ko",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://x.com/search",
        "Origin": "https://x.com",
    }
    cookies = {"auth_token": _auth_token, "ct0": _ct0}
    variables = json.dumps({
        "rawQuery": keyword,
        "count": count,
        "querySource": "typed_query",
        "product": "Latest",
    }, separators=(',', ':'))

    errors = []
    for qid in _GRAPHQL_QIDS:
        for base in ("https://x.com", "https://twitter.com"):
            url = f"{base}/i/api/graphql/{qid}/SearchTimeline"
            tag = f"[{base.split('/')[2]}:{qid[:8]}]"
            try:
                r = req.get(
                    url, headers=headers, cookies=cookies,
                    params={
                        "variables": variables,
                        "features": _FEATURES,
                        "fieldToggles": _FIELD_TOGGLES,
                    },
                    timeout=15,
                )
                if r.status_code in (400, 401, 403):
                    errors.append(f"{tag} 인증오류({r.status_code})")
                    continue
                if r.status_code == 429:
                    raise RuntimeError("Twitter 요청 한도 초과: 잠시 후 다시 시도해주세요.")
                if not r.content or not r.content.strip():
                    errors.append(f"{tag} 빈응답")
                    continue
                try:
                    data = r.json()
                except ValueError:
                    errors.append(f"{tag} JSON오류({r.status_code}): {r.text[:60]}")
                    continue

                if "errors" in data and data["errors"]:
                    msgs = "; ".join(e.get("message", "?")[:40] for e in data["errors"][:2])
                    errors.append(f"{tag} API오류: {msgs}")
                    continue

                tweets = _parse_graphql(data)
                if tweets is not None:
                    return tweets
                # Parsed OK but no tweets — might still be valid (empty results)
                if "data" in data:
                    return []
                errors.append(f"{tag} 파싱실패 keys={list(data.keys())[:4]}")
            except RuntimeError:
                raise
            except Exception as e:
                errors.append(f"{tag} 예외: {_redact(str(e))[:60]}")

    raise RuntimeError("Twitter 검색 실패: " + " / ".join(errors))


async def search_tweets(keyword: str, count: int = 30) -> list[dict]:
    if not is_ready():
        raise RuntimeError("Twitter 서비스가 설정되지 않았습니다.")
    count = min(count, MAX_COUNT)
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, lambda: _search_sync(keyword, count))
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(_redact(str(e)))
