from transformers import pipeline
from langdetect import detect, LangDetectException
import re

_pipe = None

def get_pipeline():
    global _pipe
    if _pipe is None:
        # 한국어/영어 모두 지원하는 다국어 감성분석 모델
        _pipe = pipeline(
            "text-classification",
            model="lxyuan/distilbert-base-multilingual-cased-sentiments-student",
            top_k=None,
        )
    return _pipe


def clean_text(text: str) -> str:
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"#\w+", "", text)
    return text.strip()[:512]


def detect_language(text: str) -> str:
    try:
        lang = detect(text)
        return "ko" if lang == "ko" else "en"
    except LangDetectException:
        return "unknown"


LABEL_MAP = {
    "positive": "긍정",
    "negative": "부정",
    "neutral": "중립",
}


def analyze_batch(texts: list[str]) -> list[dict]:
    pipe = get_pipeline()
    results = []
    cleaned = [clean_text(t) for t in texts]

    # 빈 텍스트 필터링 후 일괄 처리
    valid_indices = [i for i, t in enumerate(cleaned) if t]
    valid_texts = [cleaned[i] for i in valid_indices]

    if not valid_texts:
        return [{"label": "neutral", "label_ko": "중립", "score": 1.0, "language": "unknown"}] * len(texts)

    raw_results = pipe(valid_texts, batch_size=16)

    result_map = {}
    for idx, scores in zip(valid_indices, raw_results):
        best = max(scores, key=lambda x: x["score"])
        result_map[idx] = {
            "label": best["label"],
            "label_ko": LABEL_MAP.get(best["label"], best["label"]),
            "score": round(best["score"], 4),
            "language": detect_language(texts[idx]),
        }

    for i in range(len(texts)):
        if i in result_map:
            results.append(result_map[i])
        else:
            results.append({"label": "neutral", "label_ko": "중립", "score": 1.0, "language": "unknown"})

    return results


def summarize(analyzed: list[dict], items: list[dict] | None = None) -> dict:
    total = len(analyzed)
    if total == 0:
        return {"total": 0, "positive": 0, "negative": 0, "neutral": 0, "top_accounts": []}

    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for item in analyzed:
        label = item.get("label", "neutral")
        counts[label] = counts.get(label, 0) + 1

    # 언급 계정 집계 (user 또는 author 필드)
    top_accounts: list[dict] = []
    if items:
        from collections import Counter
        account_counts: Counter = Counter()
        for item in items:
            account = item.get("user") or item.get("author") or ""
            if account and account != "unknown":
                account_counts[account] += 1
        top_accounts = [
            {"account": acc, "count": cnt}
            for acc, cnt in account_counts.most_common(10)
        ]

    return {
        "total": total,
        "positive": counts["positive"],
        "negative": counts["negative"],
        "neutral": counts["neutral"],
        "positive_pct": round(counts["positive"] / total * 100, 1),
        "negative_pct": round(counts["negative"] / total * 100, 1),
        "neutral_pct": round(counts["neutral"] / total * 100, 1),
        "top_accounts": top_accounts,
    }
