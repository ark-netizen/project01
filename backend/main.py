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


@app.post("/api/translate")
def translate_text(body: dict):
    import re, requests as req
    text = str(body.get("text", ""))[:500]
    if not text:
        return {"translated": ""}
    # 간단한 언어 감지
    if re.search(r'[぀-ゟ゠-ヿ]', text):
        langpair = "ja|ko"
    elif re.search(r'[一-鿿]', text):
        langpair = "zh-CN|ko"
    else:
        langpair = "en|ko"
    try:
        r = req.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text, "langpair": langpair},
            timeout=8,
        )
        data = r.json()
        translated = data.get("responseData", {}).get("translatedText", text)
        return {"translated": translated}
    except Exception:
        return {"translated": text, "error": "번역 실패"}


@app.get("/api/debug/twitter")
def debug_twitter():
    from services.twitter_crawler import debug_info
    return debug_info()


@app.get("/api/debug/twikit-ct-source")
def debug_twikit_ct_source():
    import inspect, importlib
    try:
        mod = importlib.import_module("twikit.guest.client")
        return {"source": inspect.getsource(mod)}
    except Exception as e:
        return {"error": str(e)}


@app.api_route("/health", methods=["GET", "HEAD"])
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
