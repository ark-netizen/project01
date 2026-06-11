import re
import os
import time
import requests as _requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# HuggingFace 2024 신규 라우터 엔드포인트
HF_API_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "cardiffnlp/twitter-xlm-roberta-base-sentiment"
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


def _call_one(text: str) -> list:
    """텍스트 하나를 HF API에 전송하고 scores 리스트 반환"""
    token = os.getenv("HF_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    for attempt in range(3):
        try:
            resp = _requests.post(
                HF_API_URL,
                headers=headers,
                json={"inputs": text, "options": {"wait_for_model": True}},
                timeout=60,
            )
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
                continue
            raise RuntimeError(f"연결 실패: {e}")

        if resp.status_code == 200:
            data = resp.json()
            # [[...]] 형태로 감싸진 경우 풀기
            if data and isinstance(data[0], list):
                return data[0]
            return data
        if resp.status_code == 503:
            try:
                wait = resp.json().get("estimated_time", 20)
            except Exception:
                wait = 20
            time.sleep(min(wait, 30))
            continue
        raise RuntimeError(f"HF API 오류 {resp.status_code}: {resp.text[:200]}")

    raise RuntimeError("재시도 3회 초과")


def analyze_batch(texts: list[str]) -> list[dict]:
    cleaned = [clean_text(t) for t in texts]
    results = [{"label": "neutral", "label_ko": "중립", "score": 1.0} for _ in texts]

    valid = [(i, t) for i, t in enumerate(cleaned) if t]
    if not valid:
        return results

    # 5개씩 병렬 호출 (rate limit 고려)
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {executor.submit(_call_one, text): idx for idx, text in valid}
        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                scores = future.result()
                if not scores:
                    continue
                best = max(scores, key=lambda x: x["score"])
                label = best["label"].lower()
                results[idx] = {
                    "label": label,
                    "label_ko": LABEL_MAP.get(label, label),
                    "score": round(best["score"], 4),
                }
            except Exception as e:
                results[idx] = {
                    "label": "neutral",
                    "label_ko": "중립",
                    "score": 0.0,
                    "error": str(e),
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
