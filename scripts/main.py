"""매일 실행되는 메인 스크립트.

순서:
  1) 지난번에 처리 중이던 AI 배치가 있으면 결과 가져오기
  2) RSS에서 새 한국 관련 기사 수집 (URL·제목 기준 중복 제외)
  3) AI 처리가 안 된 기사들을 Claude 배치로 보내고 결과 반영
  4) docs/articles.json 저장 → 웹사이트가 이 파일을 읽어서 보여줌

실행: python scripts/main.py
API 키(ANTHROPIC_API_KEY)가 없으면 1·3단계를 건너뛰고 수집만 합니다.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from collect import collect_new, is_excluded, title_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_FILE = ROOT / "docs" / "articles.json"  # 기사 기록 (사이트도 이 파일을 읽음)
QUEUE_FILE = ROOT / "data" / "queue.json"        # AI 처리 대기 목록 (처리 후 삭제)
STATE_FILE = ROOT / "data" / "state.json"        # 처리 중인 배치 정보

MAX_AI_PER_RUN = 200     # 한 번에 AI로 보낼 최대 기사 수 (비용 안전장치)
MAX_ATTEMPTS = 3         # AI 처리 실패 시 재시도 횟수
BATCH_WAIT_MINUTES = 90  # 배치 결과를 기다리는 최대 시간
KEEP_DAYS = 90           # 이보다 오래된 기사는 기록에서 정리


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def article_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def main() -> None:
    now = datetime.now(timezone.utc)
    db = load_json(ARTICLES_FILE, {"updated": None, "articles": []})
    articles: dict[str, dict] = {}
    seen_keys: set[str] = set()
    for a in db["articles"]:  # 제외 규칙·중복 규칙이 바뀌어도 기존 기록에 다시 적용
        key = title_key(a["title"])
        if is_excluded(a["title"], a["url"]) or key in seen_keys:
            continue
        seen_keys.add(key)
        articles[a["id"]] = a
    queue: dict[str, dict] = load_json(QUEUE_FILE, {})
    state: dict = load_json(STATE_FILE, {})

    def save_all() -> None:
        cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat()
        kept = [a for a in articles.values() if a["published"] >= cutoff]
        kept.sort(key=lambda a: a["published"], reverse=True)
        save_json(ARTICLES_FILE, {"updated": now.isoformat(timespec="seconds"), "articles": kept})
        save_json(QUEUE_FILE, queue)
        save_json(STATE_FILE, state)

    def apply_results(ok: dict, failed: list[str]) -> None:
        for cid, ai in ok.items():
            if cid in articles:
                articles[cid].update(ai, mode="ai")
            queue.pop(cid, None)
        for cid in failed:
            if cid in queue:
                queue[cid]["attempts"] = queue[cid].get("attempts", 0) + 1
                if queue[cid]["attempts"] >= MAX_ATTEMPTS:
                    print(f"  {cid}: {MAX_ATTEMPTS}회 실패 → 원문 제목만 표시")
                    queue.pop(cid)

    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    client = None
    if has_key:
        import anthropic
        from summarize import read_results, submit_batch, wait_for_batch

        client = anthropic.Anthropic()
    else:
        print("※ ANTHROPIC_API_KEY 없음 → 무료 모드(무료 번역 + 규칙 점수)로 처리합니다")

    # 1) 지난번 배치 결과 가져오기
    if client and state.get("pending_batch"):
        bid = state["pending_batch"]
        print(f"[1] 이전 배치 확인: {bid}")
        if wait_for_batch(client, bid, max_minutes=5):
            apply_results(*read_results(client, bid))
            state.pop("pending_batch")

    # 2) 새 기사 수집
    print("[2] RSS 수집")
    seen_urls = {a["url"] for a in articles.values()}
    seen_titles = {title_key(a["title"]) for a in articles.values()}
    new_items = collect_new(seen_urls, seen_titles)
    for item in new_items:
        aid = article_id(item["url"])
        articles[aid] = {
            "id": aid,
            "url": item["url"],
            "title": item["title"],
            "source": item["source"],
            "country": item["country"],
            "published": item["published"],
            "collected": now.isoformat(timespec="seconds"),
        }
        if client:
            # 소개문은 AI 요약 재료로만 대기열에 잠시 보관 (처리 후 삭제)
            queue[aid] = {**articles[aid], "snippet": item["snippet"], "attempts": 0}
    print(f"  새 기사 합계: {len(new_items)}건 / AI 대기: {len(queue)}건")
    save_all()

    # 3-무료) API 키가 없으면 무료 번역 + 규칙 점수
    if not client:
        print("[3] 무료 모드 처리")
        from free_mode import enrich_free

        snippets = {article_id(i["url"]): i["snippet"] for i in new_items if i["snippet"]}
        enrich_free(articles, snippets, now)

    # 3) AI 처리
    if client and queue and not state.get("pending_batch"):
        print("[3] Claude 배치 처리")
        todo = sorted(queue.values(), key=lambda q: q["published"], reverse=True)[:MAX_AI_PER_RUN]
        bid = submit_batch(client, todo)
        state["pending_batch"] = bid
        save_all()  # 중간에 끊겨도 다음 실행 때 이어받을 수 있게 먼저 저장
        if wait_for_batch(client, bid, max_minutes=BATCH_WAIT_MINUTES):
            apply_results(*read_results(client, bid))
            state.pop("pending_batch")

    save_all()
    done = sum(1 for a in articles.values() if "score" in a)
    print(f"완료: 전체 {len(articles)}건 (번역·점수 처리 완료 {done}건)")


if __name__ == "__main__":
    main()
