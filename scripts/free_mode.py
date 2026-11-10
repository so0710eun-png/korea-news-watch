"""무료 모드: AI 없이 무료 번역기 + 규칙 점수로 기사를 처리합니다.

- 번역: Google 번역(비공식) → 막히면 MyMemory(하루 약 5,000자 무료) 순서로 시도.
  둘 다 실패하면 원문 제목을 그대로 두고 다음 실행 때 다시 시도합니다.
- 요약: RSS 소개문이 있는 기사만 소개문을 번역해서 보여줍니다.
- 점수: 한국어 제목의 키워드 + 여러 나라 매체가 같은 주제를 다뤘는지로 계산합니다.
"""
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

USER_AGENT = "Mozilla/5.0 (compatible; korea-news-watch/1.0)"
DAILY_CHAR_BUDGET = 4500  # MyMemory 무료 한도(약 5,000자/일) 안에서 쓰기
RESCORE_DAYS = 3          # 최근 며칠치 기사는 매번 점수를 다시 계산 (다른 나라 보도가 늘 수 있음)

# ── 점수 규칙 (여기를 고치면 점수 기준이 바뀝니다) ──────────────────
HIGH_KEYWORDS = [
    "대통령", "정부", "총리", "장관", "외교", "정상회담", "북한", "김정은", "핵무기", "핵실험",
    "비핵화", "미사일", "군사", "동맹", "주한미군", "관세", "무역", "수출", "반도체", "삼성",
    "현대차", "현대자동차", "SK", "LG", "환율", "원화", "증시", "경제", "투자", "제재", "독도",
    "위안부", "징용", "과거사", "선거", "탄핵", "국회", "검찰", "법원", "계엄", "참사",
]
SENSITIVE_KEYWORDS = ["비판", "갈등", "항의", "제재", "참사", "계엄", "탄핵", "논란", "반발", "보복"]
SOFT_KEYWORDS = [
    "드라마", "K팝", "케이팝", "아이돌", "배우", "가수", "콘서트", "영화", "예능",
    "축구", "야구", "골프", "농구", "선수", "여행", "관광", "음식", "맛집",
    "화장품", "패션", "뷰티", "브랜드",
]
COUNTRY_NAME = {"US": "미국", "JP": "일본", "CN": "중국", "VN": "베트남"}


# ── 번역 ──────────────────────────────────────────────────────────
def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def detect_lang(text: str) -> str:
    if re.search(r"[぀-ヿ]", text):           # 히라가나·가타카나
        return "ja"
    if re.search(r"[一-鿿]", text):           # 한자만
        return "zh-CN"
    if re.search(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", text, re.I):
        return "vi"
    return "en"


class Translator:
    def __init__(self):
        self.google_ok = True
        self.mymemory_ok = True
        self.chars_used = 0

    def _google(self, text: str) -> str | None:
        url = ("https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=ko&dt=t&q="
               + urllib.parse.quote(text))
        data = _get_json(url)
        return "".join(part[0] for part in data[0] if part and part[0]).strip() or None

    def _mymemory(self, text: str) -> str | None:
        if self.chars_used + len(text) > DAILY_CHAR_BUDGET:
            return None
        url = ("https://api.mymemory.translated.net/get?langpair="
               + urllib.parse.quote(f"{detect_lang(text)}|ko") + "&q=" + urllib.parse.quote(text))
        data = _get_json(url)
        if data.get("quotaFinished") or data.get("responseStatus") != 200:
            self.mymemory_ok = False
            return None
        self.chars_used += len(text)
        out = (data.get("responseData") or {}).get("translatedText", "").strip()
        return out or None

    def __call__(self, text: str) -> str | None:
        text = text.strip()[:450]
        if not text:
            return None
        if self.google_ok:
            try:
                out = self._google(text)
                time.sleep(0.5)
                if out:
                    return out
            except Exception as e:
                print(f"  Google 번역 사용 불가 → MyMemory로 전환 ({e})")
                self.google_ok = False
        if self.mymemory_ok:
            try:
                out = self._mymemory(text)
                time.sleep(1)
                return out
            except Exception as e:
                print(f"  MyMemory 번역 실패 ({e})")
                self.mymemory_ok = False
        return None


# ── 규칙 점수 ──────────────────────────────────────────────────────
def found(words: list[str], text: str) -> list[str]:
    return [w for w in words if w in text]


def rule_score(article: dict, others: list[dict]) -> tuple[int, str]:
    text = article.get("title_ko") or article["title"]
    high = found(HIGH_KEYWORDS, text)
    sensitive = found(SENSITIVE_KEYWORDS, text)
    soft = found(SOFT_KEYWORDS, text)

    # 같은 주요 키워드를 다룬 다른 나라 기사 (앞뒤 48시간)
    t = datetime.fromisoformat(article["published"])
    countries = set()
    if high:
        for o in others:
            if o["country"] == article["country"] or o["id"] == article["id"]:
                continue
            if abs(datetime.fromisoformat(o["published"]) - t) > timedelta(hours=48):
                continue
            if found(high, o.get("title_ko") or ""):
                countries.add(o["country"])

    score = 2 + min(len(high), 2) + (1 if sensitive else 0) + (1 if countries else 0)
    if soft and not high:
        score = 1
    score = max(1, min(5, score))

    parts = []
    if high:
        parts.append("키워드: " + "·".join(high[:3]))
    if sensitive:
        parts.append("민감 표현: " + "·".join(sensitive[:2]))
    if countries:
        parts.append("다른 나라 보도: " + "·".join(COUNTRY_NAME[c] for c in sorted(countries)))
    if soft and not high:
        parts.append("연예·스포츠·생활 기사")
    if not parts:
        parts.append("한국 단순 언급")
    return score, " / ".join(parts)


# ── 실행 ─────────────────────────────────────────────────────────
def enrich_free(articles: dict[str, dict], snippets: dict[str, str], now: datetime) -> None:
    """번역이 안 된 기사를 번역하고, 최근 기사 점수를 다시 계산합니다."""
    tr = Translator()
    recent_cut = (now - timedelta(days=RESCORE_DAYS)).isoformat()
    recent = [a for a in articles.values() if a["published"] >= recent_cut]
    recent.sort(key=lambda a: a["published"], reverse=True)

    # 1) 제목 번역 (최신 기사부터)
    todo = [a for a in recent if not a.get("title_ko")]
    done = 0
    for a in todo:
        ko = tr(a["title"])
        if ko:
            a["title_ko"] = ko
            done += 1
        elif not (tr.google_ok or tr.mymemory_ok):
            break
    print(f"  제목 번역: {done}/{len(todo)}건 (MyMemory 사용 {tr.chars_used}자)")

    # 2) 소개문 번역 (이번에 새로 들어온 기사 중 소개문이 있는 것만)
    sdone = 0
    for aid, snippet in snippets.items():
        a = articles.get(aid)
        if not a or not snippet or a.get("summary"):
            continue
        ko = tr(snippet[:300])
        if ko:
            a["summary"] = [ko]
            sdone += 1
        elif not (tr.google_ok or tr.mymemory_ok):
            break
    if snippets:
        print(f"  소개문 번역: {sdone}건")

    # 3) 규칙 점수 (최근 기사 전체 재계산)
    for a in recent:
        if a.get("mode") == "ai":
            continue
        a["score"], a["reason"] = rule_score(a, recent)
        a["mode"] = "free"
