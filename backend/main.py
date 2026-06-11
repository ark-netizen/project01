from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers import twitter, youtube

load_dotenv()

app = FastAPI(title="Sentiment Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://ark-netizen.github.io",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(twitter.router)
app.include_router(youtube.router)


@app.on_event("startup")
async def startup():
    from services.twitter_crawler import initialize
    await initialize()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/debug/sentiment")
def debug_sentiment():
    """감성 모델 동작 확인용 테스트 엔드포인트"""
    import os
    from services.sentiment import analyze_batch, HF_API_URL
    from services.keywords import extract_keywords

    samples = [
        "이 영상 정말 재미있고 유익했어요! 최고입니다",
        "별로예요. 완전 실망했어요",
        "그냥 그저 그런 영상이네요",
        "대박! 진짜 너무 좋다",
        "This is amazing, loved every second",
    ]

    try:
        results = analyze_batch(samples)
        kw = extract_keywords(samples)
    except Exception as e:
        return {
            "status": "error",
            "model": HF_API_URL,
            "hf_token_set": bool(os.getenv("HF_TOKEN")),
            "error": str(e),
        }

    return {
        "status": "ok",
        "model": HF_API_URL,
        "hf_token_set": bool(os.getenv("HF_TOKEN")),
        "results": [
            {"text": s, "label": r.get("label"), "label_ko": r.get("label_ko"), "score": r.get("score"), "error": r.get("error")}
            for s, r in zip(samples, results)
        ],
        "keywords": kw,
    }
