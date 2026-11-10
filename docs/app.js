// 해외 언론 속 한국 — 화면 동작 (articles.json을 읽어 목록을 그림)
const COUNTRIES = { ALL: "전체", US: "미국", JP: "일본", CN: "중국", VN: "베트남" };
const store = (() => { try { return window.localStorage; } catch { return null; } })();
const remember = (k, v) => { try { store && store.setItem(k, v); } catch {} };
const recall = (k, d) => { try { return (store && store.getItem(k)) || d; } catch { return d; } };

const state = {
  articles: [],
  country: recall("country", "ALL"),
  sort: recall("sort", "score"),
  period: recall("period", "7"),
  q: "",
};

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const highlight = (text, q) => {
  const safe = esc(text);
  if (!q) return safe;
  const re = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
  return safe.replace(re, (m) => `<mark>${m}</mark>`);
};
const fmtTime = (iso) => {
  const d = new Date(iso);
  const diff = (Date.now() - d) / 36e5;
  if (diff < 1) return "방금 전";
  if (diff < 24) return `${Math.floor(diff)}시간 전`;
  return d.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
};

function inPeriod(a) {
  const days = Number(state.period);
  return !days || Date.now() - new Date(a.published) <= days * 864e5;
}

function matches(a) {
  if (!state.q) return true;
  const hay = [a.title_ko, a.title, a.source, a.reason, ...(a.summary || [])].join(" ").toLowerCase();
  return hay.includes(state.q.toLowerCase());
}

function renderTabs() {
  const base = state.articles.filter(inPeriod);
  $("#tabs").innerHTML = Object.entries(COUNTRIES).map(([code, label]) => {
    const n = code === "ALL" ? base.length : base.filter((a) => a.country === code).length;
    return `<button role="tab" data-c="${code}" class="${state.country === code ? "on" : ""}"
      aria-selected="${state.country === code}">${label}<span class="n">${n}</span></button>`;
  }).join("");
}

function renderList() {
  let list = state.articles.filter((a) =>
    (state.country === "ALL" || a.country === state.country) && inPeriod(a) && matches(a));
  list.sort(state.sort === "score"
    ? (a, b) => (b.score || 0) - (a.score || 0) || b.published.localeCompare(a.published)
    : (a, b) => b.published.localeCompare(a.published));

  $("#count").textContent = `${list.length}건`;
  if (!list.length) {
    $("#list").innerHTML = `<p class="empty">조건에 맞는 기사가 없습니다.</p>`;
    return;
  }
  const q = state.q;
  $("#list").innerHTML = list.map((a) => {
    const s = a.score || 0;
    const title = a.title_ko || a.title;
    return `<article class="card">
      <div class="meta"><span class="flag">${esc(COUNTRIES[a.country] || a.country)}</span>
        <span>${highlight(a.source, q)}</span><time datetime="${esc(a.published)}">${fmtTime(a.published)}</time></div>
      <h2><a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${highlight(title, q)}</a></h2>
      <div class="score s${s}" title="한국 내 이슈 가능성">${s || "–"}<small>이슈</small></div>
      ${a.title_ko ? `<p class="orig">${highlight(a.title, q)}</p>` : ""}
      ${a.summary?.length
        ? `${a.mode === "free" ? `<p class="label">RSS 소개문 (자동 번역)</p>` : ""}<ul>${a.summary.map((l) => `<li>${highlight(l, q)}</li>`).join("")}</ul>`
        : (a.mode ? "" : `<p class="reason">처리 대기 중</p>`)}
      ${a.reason ? `<p class="reason"><b>${a.mode === "free" ? "규칙 점수" : "AI 점수"} ${s}</b> · ${highlight(a.reason, q)}</p>` : ""}
    </article>`;
  }).join("");
}

function render() { renderTabs(); renderList(); }

function bind() {
  $("#tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-c]");
    if (!b) return;
    state.country = b.dataset.c; remember("country", state.country); render();
  });
  document.querySelectorAll(".seg button").forEach((b) => {
    b.classList.toggle("on", b.dataset.sort === state.sort);
    b.addEventListener("click", () => {
      state.sort = b.dataset.sort; remember("sort", state.sort);
      document.querySelectorAll(".seg button").forEach((x) => x.classList.toggle("on", x === b));
      renderList();
    });
  });
  const period = $("#period");
  period.value = state.period;
  period.addEventListener("change", () => { state.period = period.value; remember("period", state.period); render(); });
  let t;
  $("#q").addEventListener("input", (e) => {
    clearTimeout(t);
    t = setTimeout(() => { state.q = e.target.value.trim(); renderList(); }, 150);
  });
}

async function init() {
  bind();
  try {
    const res = await fetch("articles.json", { cache: "no-cache" });
    const data = await res.json();
    state.articles = data.articles || [];
    if (data.updated) {
      $("#updated").textContent = `· 마지막 갱신 ${new Date(data.updated).toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" })}`;
    }
  } catch {
    $("#list").innerHTML = `<p class="empty">데이터를 불러오지 못했습니다.</p>`;
    return;
  }
  render();
}

init();
