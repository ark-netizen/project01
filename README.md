# 감성 분석 대시보드

Twitter 키워드 & YouTube 댓글을 크롤링해서 한국어/영어 감성분석을 제공하는 웹 애플리케이션.

## 기술 스택

- **Frontend**: React + Vite + Tailwind CSS + Recharts
- **Backend**: Python FastAPI
- **Twitter 크롤링**: twikit (비공식, 계정 로그인 필요)
- **YouTube 크롤링**: youtube-comment-downloader (API키 불필요)
- **감성분석 모델**: lxyuan/distilbert-base-multilingual-cased-sentiments-student

## 설치 및 실행

### 1. 백엔드 설정

```bash
cd backend
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt

# .env 파일 생성 (Twitter 로그인 정보)
copy .env.example .env
# .env 파일 편집: TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD 입력

# 서버 실행
uvicorn main:app --reload
```

### 2. 프론트엔드 설정

```bash
cd frontend
npm install
npm run dev
```

### 3. 접속

브라우저에서 `http://localhost:5173` 접속

## Twitter 로그인 설정

`twikit`은 Twitter 계정으로 로그인합니다.  
`.env` 파일에 본인 Twitter 계정 정보를 입력하면, 최초 1회 로그인 후 `twitter_cookies.json`이 생성되어 이후에는 자동 로그인됩니다.

> ⚠️ 비공식 방식이므로 자주 크롤링하면 계정 제한이 걸릴 수 있습니다.

## API 엔드포인트

- `GET /api/twitter/search?keyword=삼성&count=50`
- `POST /api/youtube/analyze` — body: `{"url": "https://...", "max_count": 100}`
