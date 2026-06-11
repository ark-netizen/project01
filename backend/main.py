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


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok"}
