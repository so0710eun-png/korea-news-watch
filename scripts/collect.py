"""RSS를 읽어서 '한국 관련' 새 기사만 골라내는 부분.

기사 본문은 가져오지 않습니다. RSS에 들어 있는 제목·링크·발행시각과
짧은 소개문(AI 요약 재료로만 잠깐 쓰고 저장하지 않음)만 사용합니다.
"""
import calendar
import html
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser

from feeds import EXCLUDE_HOST_PREFIXES, EXCLUDE_TITLE_RE, EXCLUDE_URL_RE, FEEDS, KOREA_RE

USER_AGENT = "Mozilla/5.0 (compatible; korea-news-watch/1.0; RSS reader)"
MAX_AGE_DAYS = 3  # 이보다 오래된 기사는 무시


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read()


def strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def title_key(title: str) -> str:
    """중복 판별용으로 제목을 단순화 (같은 기사가 여러 피드에 나올 때 대비).
    'オリコンニュース：' 같은 앞머리와 '（スポニチ）' 같은 꼬리표는 떼고 비교합니다."""
    t = re.sub(r"^[^：:]{1,12}ニュース[：:]", "", title.strip())
    t = re.sub(r"[（(][^）)]{1,15}[）)]$", "", t)
    return re.sub(r"\W+", "", t.lower())


def is_excluded(title: str, url: str) -> bool:
    return bool(EXCLUDE_TITLE_RE.search(title) or EXCLUDE_URL_RE.search(url))


def entry_time(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
    return None


def collect_new(seen_urls: set[str], seen_titles: set[str]) -> list[dict]:
    """모든 피드를 돌며 새 한국 관련 기사를 리스트로 돌려줍니다."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    found: list[dict] = []

    for country, feed_name, kind, url in FEEDS:
        try:
            parsed = feedparser.parse(fetch(url))
        except Exception as e:  # 피드 하나가 실패해도 나머지는 계속
            print(f"  [실패] {feed_name}: {e}")
            continue

        added = 0
        for entry in parsed.entries:
            link = (entry.get("link") or "").strip()
            title = strip_tags(entry.get("title", ""))
            if not link or not title:
                continue

            source = feed_name
            if kind == "gnews":
                src = entry.get("source") or {}
                source = src.get("title") or feed_name
                host = urlparse(src.get("href", "")).netloc
                if host.startswith(EXCLUDE_HOST_PREFIXES):
                    continue
                # Google News 제목 끝의 " - 매체명" 제거
                if source and title.endswith(f" - {source}"):
                    title = title[: -len(f" - {source}")].strip()
                snippet = ""  # Google News 소개문은 제목 반복이라 쓰지 않음
            else:
                snippet = strip_tags(entry.get("summary", ""))[:400]

            if not KOREA_RE.search(f"{title} {snippet}") or is_excluded(title, link):
                continue

            published = entry_time(entry)
            if published is None or published < cutoff:  # 날짜 없는 링크는 기사가 아닌 경우가 많음
                continue

            key = title_key(title)
            if link in seen_urls or key in seen_titles:
                continue
            seen_urls.add(link)
            seen_titles.add(key)

            found.append({
                "url": link,
                "title": title,
                "source": source,
                "country": country,
                "published": published.isoformat(timespec="seconds"),
                "snippet": snippet,
            })
            added += 1
        print(f"  {feed_name}: 피드 {len(parsed.entries)}건 → 새 한국 기사 {added}건")

    return found
