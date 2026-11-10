"""수집할 피드 목록과 '한국 관련' 판별 키워드.

매체를 추가/삭제하고 싶으면 이 파일만 고치면 됩니다.
- kind="rss"   : 매체가 직접 제공하는 RSS
- kind="gnews" : Google News 검색 RSS (자체 RSS가 없거나 막힌 매체를 site: 로 묶어 검색)
모든 피드는 2026-11-10에 실제 접속해 작동을 확인했습니다.
"""
import re
from urllib.parse import quote_plus

COUNTRIES = {
    "US": "미국",
    "JP": "일본",
    "CN": "중국",
    "VN": "베트남",
}


def gnews(query: str, hl: str, gl: str, ceid: str) -> str:
    """Google News 검색 RSS 주소 만들기. when:1d = 최근 하루치."""
    return (
        "https://news.google.com/rss/search?q="
        + quote_plus(f"{query} when:1d")
        + f"&hl={hl}&gl={gl}&ceid={ceid}"
    )


FEEDS = [
    # ── 미국 ─────────────────────────────────────────────
    ("US", "NYT Asia", "rss", "https://rss.nytimes.com/services/xml/rss/nyt/AsiaPacific.xml"),
    ("US", "CNN Asia", "rss", "http://rss.cnn.com/rss/edition_asia.rss"),
    ("US", "NPR World", "rss", "https://feeds.npr.org/1004/rss.xml"),
    ("US", "미국 주요 매체", "gnews", gnews(
        "Korea (site:apnews.com OR site:nytimes.com OR site:washingtonpost.com"
        " OR site:wsj.com OR site:bloomberg.com OR site:cnn.com)",
        "en-US", "US", "US:en")),
    # ── 일본 ─────────────────────────────────────────────
    ("JP", "NHK 国際", "rss", "https://www3.nhk.or.jp/rss/news/cat6.xml"),
    ("JP", "Nikkei Asia", "rss", "https://asia.nikkei.com/rss/feed/nar"),
    ("JP", "Japan Times", "rss", "https://www.japantimes.co.jp/feed/"),
    ("JP", "일본 주요 매체", "gnews", gnews(
        "韓国 (site:nikkei.com OR site:asahi.com OR site:yomiuri.co.jp"
        " OR site:mainichi.jp OR site:nhk.or.jp OR site:kyodo.co.jp)",
        "ja", "JP", "JP:ja")),
    # ── 중국 (홍콩 SCMP 포함) ────────────────────────────
    ("CN", "SCMP Asia", "rss", "https://www.scmp.com/rss/3/feed"),
    ("CN", "Xinhua English", "rss", "http://www.xinhuanet.com/english/rss/worldrss.xml"),
    ("CN", "Global Times", "rss", "https://www.globaltimes.cn/rss/outbrain.xml"),
    ("CN", "중국 매체(영문)", "gnews", gnews(
        "Korea (site:scmp.com OR site:english.news.cn OR site:globaltimes.cn"
        " OR site:chinadaily.com.cn OR site:cgtn.com)",
        "en-US", "US", "US:en")),
    ("CN", "중국 매체(중문)", "gnews", gnews(
        "韩国 (site:xinhuanet.com OR site:news.cn OR site:people.com.cn"
        " OR site:chinanews.com.cn OR site:cctv.com OR site:thepaper.cn)",
        "zh-CN", "CN", "CN:zh-Hans")),
    # ── 베트남 ───────────────────────────────────────────
    ("VN", "VnExpress International", "rss", "https://e.vnexpress.net/rss/news.rss"),
    ("VN", "VnExpress Thế giới", "rss", "https://vnexpress.net/rss/the-gioi.rss"),
    ("VN", "Tuổi Trẻ Thế giới", "rss", "https://tuoitre.vn/rss/the-gioi.rss"),
    ("VN", "Thanh Niên Thế giới", "rss", "https://thanhnien.vn/rss/the-gioi.rss"),
    ("VN", "베트남 주요 매체", "gnews", gnews(
        '"Hàn Quốc" (site:vnexpress.net OR site:tuoitre.vn OR site:thanhnien.vn'
        " OR site:vietnamnet.vn OR site:vov.vn OR site:dantri.com.vn)",
        "vi", "VN", "VN:vi")),
]

# 제목(+RSS 소개문)에 이 중 하나라도 있으면 '한국 관련'으로 봅니다.
KOREA_KEYWORDS = [
    # 영어
    r"\bKoreas?\b", r"\bKorean", r"\bSeoul\b", r"\bPyongyang\b", r"\bBusan\b",
    # 일본어
    "韓国", "日韓", "韓日", "訪韓", "米韓", "韓米", "ソウル", "北朝鮮", "朝鮮半島",
    # 중국어(간체)
    "韩国", "中韩", "韩中", "美韩", "韩美", "日韩", "韩日", "朝韩", "韩方", "首尔", "朝鲜",
    # 베트남어
    "Hàn Quốc", "Triều Tiên", "Bình Nhưỡng", r"Việt\s*-\s*Hàn", r"Hàn\s*-\s*Việt",
]
KOREA_RE = re.compile("|".join(KOREA_KEYWORDS), re.IGNORECASE)

# 같은 사이트라도 요리·게임·연예 섹션 같은 곳은 제외
EXCLUDE_HOST_PREFIXES = ("cooking.", "game.", "career.", "ngoisao.", "cuoi.")

# 기사가 아닌 것(보도자료, 특집 코너 페이지)은 제외
EXCLUDE_TITLE_RE = re.compile(r"プレスリリース|PR TIMES|新闻稿|Thông cáo báo chí")
EXCLUDE_URL_RE = re.compile(r"/specials/|/fast-facts/|---fast-facts")
