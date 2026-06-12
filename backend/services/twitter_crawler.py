import os
import json
import base64
import hashlib
import asyncio
import time
import urllib.parse
from typing import Optional

try:
    from playwright.async_api import async_playwright, BrowserContext, Playwright, Browser
    _PLAYWRIGHT_OK = True
except ImportError:
    _PLAYWRIGHT_OK = False

try:
    from playwright_stealth import stealth_async
    _STEALTH_OK = True
except ImportError:
    _STEALTH_OK = False

_pw: Optional["Playwright"] = None
_browser: Optional["Browser"] = None
_context: Optional["BrowserContext"] = None
_lock = asyncio.Lock()
_needs_relogin = False
_init_error: str = ""
_cache: dict = {}
CACHE_TTL = 300  # 5분


async def initialize() -> None:
    global _pw, _browser, _context, _needs_relogin, _init_error

    if not _PLAYWRIGHT_OK:
        _init_error = "playwright_not_installed"
        return

    cookies_raw = os.getenv("TWITTER_COOKIES", "").strip()
    if not cookies_raw:
        _needs_relogin = True
        _init_error = "no_cookies_env"
        return

    try:
        try:
            data = base64.b64decode(cookies_raw).decode()
        except Exception:
            data = cookies_raw
        cookies = json.loads(data)
    except Exception as e:
        _needs_relogin = True
        _init_error = f"cookie_parse_error: {type(e).__name__}"
        return

    try:
        _pw = await async_playwright().start()
        _browser = await _pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        _context = await _browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
            locale="ko-KR",
        )
        await _context.add_cookies(cookies)
        _init_error = "ok"

    except Exception as e:
        _needs_relogin = True
        _init_error = f"browser_launch_error: {type(e).__name__}: {str(e)[:120]}"


def is_ready() -> bool:
    return _context is not None and not _needs_relogin


def relogin_required() -> bool:
    return _needs_relogin


async def search_tweets(keyword: str, count: int = 30) -> list[dict]:
    global _needs_relogin

    if _needs_relogin:
        raise RuntimeError("Twitter 세션 만료: 쿠키를 갱신해주세요.")
    if not is_ready():
        raise RuntimeError("Twitter 서비스가 초기화되지 않았습니다.")

    count = min(count, 50)

    cache_key = hashlib.md5(f"{keyword}:{count}".encode()).hexdigest()
    cached = _cache.get(cache_key)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]

    async with _lock:
        cached = _cache.get(cache_key)
        if cached and time.time() - cached[0] < CACHE_TTL:
            return cached[1]

        tweets = await _do_search(keyword, count)
        _cache[cache_key] = (time.time(), tweets)
        return tweets


async def _do_search(keyword: str, count: int) -> list[dict]:
    global _needs_relogin

    page = await _context.new_page()
    captured: list[dict] = []

    async def on_response(response):
        if "SearchTimeline" not in response.url:
            return
        try:
            data = await response.json()
            parsed = _parse_graphql(data)
            if parsed:
                captured.extend(parsed)
        except Exception:
            pass

    if _STEALTH_OK:
        await stealth_async(page)
    page.on("response", on_response)

    try:
        encoded = urllib.parse.quote(keyword)
        await page.goto(
            f"https://x.com/search?q={encoded}&src=typed_query&f=live",
            wait_until="networkidle",
            timeout=25000,
        )
        await asyncio.sleep(1.5)

        if "/login" in page.url or "/i/flow" in page.url:
            _needs_relogin = True
            raise RuntimeError("Twitter 세션 만료: 쿠키를 갱신해주세요.")

        return captured[:count]

    finally:
        await page.close()


def _parse_graphql(data: dict) -> list[dict]:
    try:
        instructions = (
            data["data"]["search_by_raw_query"]
               ["search_timeline"]["timeline"]["instructions"]
        )
    except (KeyError, TypeError):
        return []

    tweets = []
    for inst in instructions:
        t = inst.get("type", "")
        if t == "TimelineAddEntries":
            entries = inst.get("entries", [])
        elif t == "TimelineAddToModule":
            entries = inst.get("moduleItems", [])
        else:
            continue
        for entry in entries:
            content = entry.get("content") or entry.get("item") or {}
            ic = content.get("itemContent", {})
            if ic.get("itemType") != "TimelineTweet":
                continue
            result = ic.get("tweet_results", {}).get("result", {})
            if not result:
                continue
            if result.get("__typename") == "TweetWithVisibilityResults":
                result = result.get("tweet", result)
            leg = result.get("legacy", {})
            uleg = (result.get("core", {})
                         .get("user_results", {})
                         .get("result", {})
                         .get("legacy", {}))
            if not leg:
                continue
            tweets.append({
                "id": leg.get("id_str", ""),
                "text": leg.get("full_text") or leg.get("text", ""),
                "user": uleg.get("screen_name", "unknown"),
                "created_at": leg.get("created_at", ""),
                "likes": leg.get("favorite_count", 0),
                "retweets": leg.get("retweet_count", 0),
            })
    return tweets
