"""
로컬에서 실행해서 Twitter 쿠키를 생성하는 스크립트.

사용법:
  pip install twikit
  python gen_cookies.py

완료되면 출력된 base64 문자열을 Render 환경변수 TWITTER_COOKIES 에 붙여넣으세요.
"""

import asyncio
import base64
import twikit


async def main():
    username = input("Twitter 아이디(username, @ 제외): ").strip()
    email    = input("이메일: ").strip()
    password = input("비밀번호: ").strip()

    print("\n로그인 중...")
    client = twikit.Client("ko-KR")
    await client.login(
        auth_info_1=username,
        auth_info_2=email,
        password=password,
    )
    client.save_cookies("cookies.json")
    print("cookies.json 저장 완료")

    with open("cookies.json", "r", encoding="utf-8") as f:
        data = f.read()
    encoded = base64.b64encode(data.encode()).decode()

    print("\n" + "="*60)
    print("Render 환경변수에 추가하세요:")
    print("  Key  : TWITTER_COOKIES")
    print("  Value: (아래 줄 전체 복사)")
    print("="*60)
    print(encoded)
    print("="*60 + "\n")


asyncio.run(main())
