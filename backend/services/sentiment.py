import re
import os
import httpx

HF_API_URL = (
    "https://api-inference.huggingface.co/models/"
    "lxyuan/distilbert-base-multilingual-cased-sentiments-student"
)

LABEL_MAP = {
    "positive": "긍정",
    "negative": "부정",
    "neutral": "중립",
}


def clean_text(text: str) -> str:
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"#\w+", "", text)
    return text.strip()[:512]


def _call_hf(texts: list[str]) -> list[dict]:
    token = os.getenv("HF_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    with httpx.Client(timeout=120) as client:
        for attempt in range(3):
            resp = client.post(
                HF_API_URL,
                headers=headers,
                json={"inputs": texts, "options": {"wait_for_model": True}},
            )
            if resp.status_code == 200:
                return resp.json()
            # 모델 로딩 중 (503) → 대기 후 재시도
            if resp.status_code == 503:
                import time
                wait = resp.json().get("estimated_time", 20)
                time.sleep(min(wait, 30))
                continue
            raise RuntimeError(f"HuggingFace API 오류 {resp.status_code}: {resp.text[:200]}")

    raise RuntimeError("HuggingFace API 재시도 초과")


def analyze_batch(texts: list[str]) -> list[dict]:
    cleaned = [clean_text(t) for t in texts]

    # 빈 텍스트 인덱스 처리
    valid = [(i, t) for i, t in enumerate(cleaned) if t]
    results = [{"label": "neutral", "label_ko": "중립", "score": 1.0}] * len(texts)

    if not valid:
        return results

    # HF API는 한 번에 100건 제한 → 50건씩 배치
    BATCH = 50
    for start in range(0, len(valid), BATCH):
        chunk = valid[start:start + BATCH]
        indices, inputs = zip(*chunk)

        try:
            raw = _call_hf(list(inputs))
        except Exception as e:
            err_msg = str(e)
            for idx in indices:
                results[idx] = {"label": "neutral", "label_ko": "중립", "score": 0.0, "error": err_msg}
            continue

        # 단일 입력이면 list[dict], 복수면 list[list[dict]]
        if isinstance(raw[0], dict):
            raw = [raw]

        for idx, scores in zip(indices, raw):
            best = max(scores, key=lambda x: x["score"])
            results[idx] = {
                "label": best["label"],
                "label_ko": LABEL_MAP.get(best["label"], best["label"]),
                "score": round(best["score"], 4),
            }

    return results


def summarize(analyzed: list[dict], items: list[dict] | None = None) -> dict:
    total = len(analyzed)
    if total == 0:
        return {"total": 0, "positive": 0, "negative": 0, "neutral": 0, "top_accounts": []}

    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for item in analyzed:
        label = item.get("label", "neutral")
        counts[label] = counts.get(label, 0) + 1

    top_accounts: list[dict] = []
    if items:
        from collections import Counter
        counter: Counter = Counter()
        for item in items:
            account = item.get("user") or item.get("author") or ""
            if account and account != "unknown":
                counter[account] += 1
        top_accounts = [{"account": a, "count": c} for a, c in counter.most_common(10)]

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
