"""무료 모드: AI 없이 무료 번역기로 제목과 RSS 소개문을 한국어로 옮깁니다.

- 번역: Google 번역(비공식) → 막히면 MyMemory(하루 약 5,000자 무료) 순서로 시도.
  둘 다 실패하면 원문 제목을 그대로 두고 다음 실행 때 다시 시도합니다.
- 요약: RSS 소개문이 있는 기사만 소개문을 번역해서 보여줍니다.
- 화제성 점수는 topic.py가 매깁니다 (무료/Claude 모드 공통).
"""
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

USER_AGENT = "Mozilla/5.0 (compatible; korea-news-watch/1.0)"
DAILY_CHAR_BUDGET = 4500  # MyMemory 무료 한도(약 5,000자/일) 안에서 쓰기
RETRY_DAYS = 3            # 번역 실패한 기사는 이 기간 동안 다음 실행 때 다시 시도


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


# ── 실행 ─────────────────────────────────────────────────────────
def enrich_free(articles: dict[str, dict], snippets: dict[str, str], now: datetime) -> None:
    """번역이 안 된 기사의 제목과, 새 기사의 RSS 소개문을 번역합니다."""
    tr = Translator()
    recent_cut = (now - timedelta(days=RETRY_DAYS)).isoformat()
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

    for a in recent:
        if a.get("title_ko") and a.get("mode") != "ai":
            a["mode"] = "free"
