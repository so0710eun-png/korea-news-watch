"""화제성 점수와 한국/북한 분류.

1) 같은 이야기 묶기: 한국어 제목(번역본)을 두 글자 단위로 쪼개 비교합니다.
   나라·언어가 달라도 한국어 번역 제목이 비슷하면 같은 이야기로 봅니다.
   예) 베트남 VietNamNet + Dân trí + 홍콩 SCMP의 "북한 무기 보려고 국경에 몰린 관광객" 기사 → 한 묶음
2) 화제성: 그 이야기를 다룬 매체 수 + 나라 수로 1~5점. 키워드는 보지 않습니다.
3) 한국/북한: 제목에 북한 관련 표현이 있으면 '북한', 그 밖의 한국 언급이 있으면 '한국'(둘 다일 수 있음).
"""
import math
import re
from datetime import datetime, timedelta

SIM_THRESHOLD = 0.35   # 실제 수집 기사로 시험해 정한 값 (낮추면 더 많이 묶이고, 높이면 덜 묶임)
PAIR_HOURS = 72        # 이 시간 안에 나온 기사끼리만 같은 이야기 후보
RECENT_DAYS = 7        # 최근 며칠치를 매 실행마다 다시 묶음

COUNTRY_NAME = {"US": "미국", "JP": "일본", "CN": "중국", "VN": "베트남"}

# 어디에나 나와서 '같은 이야기' 판단에 도움이 안 되는 두 글자
STOP_BIGRAMS = {
    "한국", "국의", "국은", "국이", "국과", "국에", "북한", "한은", "한이", "한의", "일본", "본의",
    "중국", "미국", "베트남", "트남", "있습", "습니", "니다", "했다", "한다", "에서", "으로",
    "보도", "기사", "뉴스", "대한", "합니", "됩니", "있다", "이다", "하는",
}

NK_RE = re.compile(
    r"North Korean?s?|Pyongyang|Kim Jong[- ]?Un|DPRK|北朝鮮|金正恩|平壌|朝鲜|平壤|"
    r"Triều Tiên|Bình Nhưỡng|Kim Jong-un|북한|김정은|(?<!태)평양",  # '태평양'은 제외
    re.IGNORECASE,
)
SK_RE = re.compile(r"Korea|Seoul|Busan|韓|ソウル|韩|首尔|Hàn Quốc|한국|남한|서울", re.IGNORECASE)


def korea_tags(title: str, title_ko: str) -> list[str]:
    text = f"{title} {title_ko}"
    tags = []
    if NK_RE.search(text):
        tags.append("north")
    if SK_RE.search(NK_RE.sub(" ", text)) or not tags:
        tags.insert(0, "south")
    return tags


def tokens(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[가-힣]+|[A-Za-z0-9]{2,}", text):
        if re.fullmatch(r"[A-Za-z0-9]+", w):
            out.add(w.lower())
            continue
        for i in range(len(w) - 1):
            b = w[i:i + 2]
            if b not in STOP_BIGRAMS:
                out.add(b)
    return out


def heat_score(n_sources: int, n_countries: int) -> tuple[float, int]:
    heat = n_sources + 1.5 * (n_countries - 1)
    if heat < 1.5:
        score = 1
    elif heat < 3:
        score = 2
    elif heat < 5:
        score = 3
    elif heat < 8:
        score = 4
    else:
        score = 5
    return heat, score


def assign(articles: dict[str, dict], now: datetime) -> None:
    for a in articles.values():
        a["korea"] = korea_tags(a["title"], a.get("title_ko", ""))

    cut = (now - timedelta(days=RECENT_DAYS)).isoformat()
    recent = sorted((a for a in articles.values() if a["published"] >= cut),
                    key=lambda a: a["published"])
    n = len(recent)
    toks = [tokens(a.get("title_ko") or a["title"]) for a in recent]
    times = [datetime.fromisoformat(a["published"]) for a in recent]

    # 드물게 나오는 글자 조합일수록 가중치를 크게 (IDF)
    df: dict[str, int] = {}
    for t in toks:
        for b in t:
            df[b] = df.get(b, 0) + 1
    idf = {b: math.log((n + 1) / (c + 0.5)) for b, c in df.items()}
    weight = [sum(idf[b] for b in t) for t in toks]

    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if times[j] - times[i] > timedelta(hours=PAIR_HOURS):
                break  # 시간순 정렬이라 이후는 더 멀다
            shared = toks[i] & toks[j]
            if len(shared) < 2:
                continue
            denom = min(weight[i], weight[j])
            if denom > 0 and sum(idf[b] for b in shared) / denom >= SIM_THRESHOLD:
                parent[find(j)] = find(i)

    groups: dict[int, list[dict]] = {}
    for i, a in enumerate(recent):
        groups.setdefault(find(i), []).append(a)

    for members in groups.values():
        sources = {m["source"] for m in members}
        by_country: dict[str, int] = {}
        for m in members:
            by_country[m["country"]] = by_country.get(m["country"], 0) + 1
        heat, score = heat_score(len(sources), len(by_country))
        cluster_id = members[0]["id"]  # 가장 먼저 나온 기사의 id
        detail = ", ".join(f"{COUNTRY_NAME.get(c, c)} {k}" for c, k in
                           sorted(by_country.items(), key=lambda x: -x[1]))
        reason = (f"{len(sources)}개 매체 · {len(by_country)}개국 보도 ({detail})"
                  if len(members) > 1 else "단독 보도")
        for m in members:
            m.update(cluster=cluster_id, heat=round(heat, 1), score=score, reason=reason)
