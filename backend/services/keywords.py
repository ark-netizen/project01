import re
from collections import Counter

KOREAN_STOPWORDS = {
    '이', '가', '은', '는', '을', '를', '의', '에', '에서', '로', '으로', '와', '과',
    '이다', '있다', '하다', '되다', '것', '수', '그', '저', '제', '들', '도', '만',
    '더', '좀', '잘', '못', '안', '왜', '어', '이런', '저런', '그런', '어떤', '무슨',
    '하지만', '그리고', '또는', '그러나', '그래서', '또', '다시', '진짜', '정말',
    '너무', '매우', '아주', '조금', '많이', '나', '너', '우리', '저', '그', '그녀',
    '그들', '여러분', '이게', '이거', '그게', '그거', '저게', '저거', '여기', '거기',
    '저기', '지금', '이제', '아직', '벌써', '이미', '항상', '가끔', '자꾸', '계속',
    '같은', '다른', '새로운', '좋은', '나쁜', '큰', '작은', '많은', '적은',
    '때', '곳', '분', '명', '개', '번', '번째', '할', '한', '하는', '되는',
    '있는', '없는', '같이', '처럼', '보다', '부터', '까지', '이후', '이전',
    '영상', '동영상', '댓글', '유튜브', '채널', '구독', '좋아요', '싫어요',
    '감사', '감사합니다', '감사해요', '고맙습니다', '고마워요',
    '봤어요', '봤습니다', '보다', '보세요', '봐요',
    '했어요', '했습니다', '해요', '해줘요', '해주세요',
    '이에요', '입니다', '이야', '이야요',
    '완전', '진짜로', '너무나', '되게', '엄청',
    'ㅋ', 'ㅠ', 'ㅎ', 'ㄷ', 'ㅇ', 'ㅜ', 'ㅡ',
}

ENGLISH_STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'this', 'that', 'these', 'those', 'it', 'its',
    'he', 'she', 'they', 'we', 'i', 'you', 'my', 'your', 'his', 'her',
    'our', 'their', 'what', 'which', 'who', 'how', 'when', 'where', 'why',
    'not', 'no', 'so', 'if', 'as', 'up', 'out', 'about', 'than', 'then',
    'just', 'very', 'also', 'really', 'get', 'got', 'like', 'can', 'im',
    'its', 'ive', 'dont', 'cant', 'wont', 'isnt', 'arent',
    'good', 'great', 'nice', 'love', 'wow', 'yes', 'yeah', 'ok', 'okay',
    'thanks', 'thank', 'lol', 'omg', 'bro', 'dude', 'man', 'guys',
    'come', 'see', 'know', 'think', 'way', 'time', 'go', 'make',
    'one', 'two', 'first', 'last', 'new', 'old', 'big', 'little',
    'more', 'most', 'much', 'many', 'some', 'any', 'all', 'every',
    'been', 'being', 'still', 'too', 'even', 'well', 'back', 'same',
    'hi', 'hey', 'oh', 'ah', 'uh', 'um',
}

STOPWORDS = KOREAN_STOPWORDS | ENGLISH_STOPWORDS

HAS_KOREAN = re.compile(r'[가-힣ㄱ-ㅎㅏ-ㅣ]')


def _has_korean(word: str) -> bool:
    return bool(HAS_KOREAN.search(word))


def extract_keywords(texts: list[str], top_n: int = 20) -> list[dict]:
    counter: Counter = Counter()

    for text in texts:
        text = re.sub(r'http\S+', '', text)
        text = re.sub(r'@\w+', '', text)
        text = re.sub(r'#(\w+)', r'\1', text)
        text = re.sub(r'[^\w\s가-힣ㄱ-ㅎㅏ-ㅣ]', ' ', text)

        for word in text.lower().split():
            word = word.strip()
            if len(word) < 2:
                continue
            if word.isdigit():
                continue
            if word in STOPWORDS:
                continue
            # 영어 단어는 5글자 미만이면 제외 (한국어는 제외 안 함)
            if not _has_korean(word) and len(word) < 5:
                continue
            counter[word] += 1

    # 한국어 포함 단어를 우선 정렬 (빈도수 동일 시 한국어 우선)
    sorted_words = sorted(counter.items(), key=lambda x: (x[1], _has_korean(x[0])), reverse=True)
    return [{'word': w, 'count': c} for w, c in sorted_words[:top_n]]
