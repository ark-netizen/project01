"""
로컬에서 실행해서 Twitter 쿠키를 생성하는 스크립트.

사용법:
  pip install playwright
  playwright install chromium
  python gen_cookies.py

완료되면 출력된 base64 문자열을 Render 환경변수 TWITTER_COOKIES 에 붙여넣으세요.
"""

import asyncio
import json
import base64
from playwright.async_api import async_playwright


async def main():
    print("브라우저를 시작합니다...")
    print("X.com 로그인 창이 열리면 직접 로그인하세요.")
    print("로그인 완료 후 홈 화면이 보이면 자동으로 쿠키를 저장합니다.\n")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()
        await page.goto("https://x.com/login")

        # 로그인 완료 감지: /home 으로 이동될 때까지 대기 (최대 3분)
        print("로그인을 기다리는 중... (최대 3분)")
        try:
            await page.wait_for_url("**/home", timeout=180000)
        except Exception:
            print("시간 초과 또는 오류. 현재 URL:", page.url)
            await browser.close()
            return

        print("로그인 감지됨. 쿠키 저장 중...")
        cookies = await context.cookies()
        await browser.close()

    # 민감 쿠키만 필터 (auth_token, ct0 포함 여부 확인)
    names = {c["name"] for c in cookies}
    if "auth_token" not in names:
        print("auth_token 쿠키를 찾을 수 없습니다. 로그인이 완료되지 않은 것 같습니다.")
        return

    with open("cookies.json", "w", encoding="utf-8") as f:
        json.dump(cookies, f)
    print("cookies.json 저장 완료")

    encoded = base64.b64encode(json.dumps(cookies).encode()).decode()

    print("\n" + "=" * 60)
    print("Render 환경변수에 추가하세요:")
    print("  Key  : TWITTER_COOKIES")
    print("  Value: (아래 줄 전체 복사)")
    print("=" * 60)
    print(encoded)
    print("=" * 60 + "\n")
    print("주의: 이 값은 로그인 세션입니다. 공개 장소에 절대 공유하지 마세요.")


asyncio.run(main())
