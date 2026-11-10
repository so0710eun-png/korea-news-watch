// 해외 언론 속 한국 — 화면 동작 (articles.json을 읽어 목록을 그림)
const TOPICS = { all: "전체", south: "한국", north: "북한", saved: "★ 저장" };
const COUNTRIES = { ALL: "모든 나라", US: "미국", JP: "일본", CN: "중국", VN: "베트남" };
const store = (() => { try { return window.localStorage; } catch { return null; } })();
const remember = (k, v) => { try { store && store.setItem(k, v); } catch {} };
const recall = (k, d) => { try { return (store && store.getItem(k)) || d; } catch { return d; } };

const state = {
  articles: [],
  topic: recall("topic", "all"),
  country: recall("country2", "ALL"),
  sort: recall("sort2", "heat"),
  period: recall("period", "7"),
  q: "",
};

// ── 저장(별표) : 이 브라우저에만 보관 ─────────────────────────
const loadSaved = () => { try { return JSON.parse(recall("saved", "{}")) || {}; } catch { return {}; } };
let saved = loadSaved();
const persistSaved = () => remember("saved", JSON.stringify(saved));
const SAVE_FIELDS = ["id", "url", "title", "title_ko", "source", "country", "published", "korea", "summary", "mode"];
function toggleSave(id) {
  if (saved[id]) { delete saved[id]; }
  else {
    const a = state.articles.find((x) => x.id === id);
    if (!a) return;
    saved[id] = Object.fromEntries(SAVE_FIELDS.map((k) => [k, a[k]]));
    saved[id].savedAt = new Date().toISOString();
  }
  persistSaved();
  render();
}
const savedList = () => Object.values(saved).sort((a, b) => b.savedAt.localeCompare(a.savedAt));

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const highlight = (text, q) => {
  const safe = esc(text);
  if (!q) return safe;
  const re = new RegExp(esc(q).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
  return safe.replace(re, (m) => `<mark>${m}</mark>`);
};
const fmtTime = (iso) => {
  const d = new Date(iso);
  const diff = (Date.now() - d) / 36e5;
  if (diff < 1) return "방금 전";
  if (diff < 24) return `${Math.floor(diff)}시간 전`;
  return d.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
};

const tagsOf = (a) => a.korea || ["south"];
const inPeriod = (a) => { const d = Number(state.period); return !d || Date.now() - new Date(a.published) <= d * 864e5; };
const inTopic = (a, t) => t === "all" || tagsOf(a).includes(t);
const inCountry = (a) => state.country === "ALL" || a.country === state.country;
const matches = (a) => {
  if (!state.q) return true;
  const hay = [a.title_ko, a.title, a.source, ...(a.summary || [])].join(" ").toLowerCase();
  return hay.includes(state.q.toLowerCase());
};

// 같은 이야기(cluster)끼리 묶어서 카드 하나로
function groupStories(list) {
  const map = new Map();
  for (const a of list) {
    const key = a.cluster || a.id;
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(a);
  }
  return [...map.values()].map((items) => {
    items.sort((x, y) => (y.summary?.length ? 1 : 0) - (x.summary?.length ? 1 : 0) || y.published.localeCompare(x.published));
    const latest = items.reduce((m, x) => (x.published > m ? x.published : m), items[0].published);
    return { main: items[0], others: items.slice(1), latest, heat: items[0].heat || 1, score: items[0].score || 1 };
  });
}

function storiesFor(topic) {
  if (topic === "saved") {  // 저장한 기사는 묶지 않고, 기간과 상관없이 저장한 순서대로
    return savedList().filter((a) => inCountry(a) && matches(a))
      .map((a) => ({ main: a, others: [], latest: a.published, heat: 0, score: 0, savedAt: a.savedAt }));
  }
  return groupStories(state.articles.filter((a) => inTopic(a, topic) && inCountry(a) && inPeriod(a) && matches(a)));
}

// 저장한 기사를 보고서에 붙여넣기 좋은 글로 만들기
function clippingText() {
  return savedList().map((a, i) => {
    const d = new Date(a.published).toLocaleDateString("ko-KR");
    const lines = [`${i + 1}. [${COUNTRIES[a.country] || a.country}·${a.source}] ${a.title_ko || a.title} (${d})`];
    if (a.title_ko) lines.push(`   원제: ${a.title}`);
    (a.summary || []).forEach((s) => lines.push(`   - ${s}`));
    lines.push(`   ${a.url}`);
    return lines.join("\n");
  }).join("\n\n");
}

function renderTabs() {
  $("#tabs").innerHTML = Object.entries(TOPICS).map(([code, label]) =>
    `<button role="tab" data-t="${code}" class="${state.topic === code ? "on" : ""}" aria-selected="${state.topic === code}">
      ${label}<span class="n">${storiesFor(code).length}</span></button>`).join("");
  $("#countries").innerHTML = Object.entries(COUNTRIES).map(([code, label]) =>
    `<button data-c="${code}" class="${state.country === code ? "on" : ""}">${label}</button>`).join("");
}

function renderList() {
  const isSaved = state.topic === "saved";
  const stories = storiesFor(state.topic);
  if (!isSaved) {
    stories.sort(state.sort === "heat"
      ? (a, b) => b.heat - a.heat || b.latest.localeCompare(a.latest)
      : (a, b) => b.latest.localeCompare(a.latest));
  }

  const nArticles = stories.reduce((n, s) => n + 1 + s.others.length, 0);
  $("#count").textContent = isSaved ? `저장한 기사 ${stories.length}건` : `이야기 ${stories.length}개 · 기사 ${nArticles}건`;
  const toolbar = isSaved && stories.length
    ? `<div class="toolbar"><button id="copyClip">📋 클리핑 복사</button><button id="clearSaved">모두 지우기</button></div>` : "";
  if (!stories.length) {
    $("#list").innerHTML = `<p class="empty">${isSaved ? "아직 저장한 기사가 없습니다. 기사 카드의 ☆를 눌러 저장하세요." : "조건에 맞는 기사가 없습니다."}</p>`;
    return;
  }
  const q = state.q;
  $("#list").innerHTML = toolbar + stories.map(({ main: a, others, score, savedAt }) => {
    const title = a.title_ko || a.title;
    const tags = tagsOf(a).map((t) => `<span class="tag ${t}">${TOPICS[t]}</span>`).join("");
    const on = !!saved[a.id];
    return `<article class="card">
      <div class="meta">${tags}<span class="flag">${esc(COUNTRIES[a.country] || a.country)}</span>
        <span>${highlight(a.source, q)}</span><time datetime="${esc(a.published)}">${fmtTime(a.published)}</time>
        <button class="star ${on ? "on" : ""}" data-save="${esc(a.id)}" aria-pressed="${on}"
          title="${on ? "저장 취소" : "저장하기"}">${on ? "★" : "☆"}</button></div>
      <h2><a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${highlight(title, q)}</a></h2>
      ${score ? `<div class="score s${score}" title="화제성 (보도한 매체·나라 수)">${score}<small>화제</small></div>` : ""}
      ${savedAt ? `<p class="saved-note">${new Date(savedAt).toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" })} 저장</p>` : ""}
      ${a.title_ko ? `<p class="orig">${highlight(a.title, q)}</p>` : ""}
      ${a.summary?.length
        ? `${a.mode === "free" ? `<p class="label">RSS 소개문 (자동 번역)</p>` : ""}<ul>${a.summary.map((l) => `<li>${highlight(l, q)}</li>`).join("")}</ul>`
        : ""}
      ${a.reason ? `<p class="reason">${esc(a.reason)}</p>` : ""}
      ${others.length ? `<details class="related"><summary>관련 보도 ${others.length}건 더 보기</summary><ul>${
        others.map((o) => `<li><span class="flag">${esc(COUNTRIES[o.country] || o.country)}</span> ${esc(o.source)} ·
          <a href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">${highlight(o.title_ko || o.title, q)}</a></li>`).join("")
      }</ul></details>` : ""}
    </article>`;
  }).join("");
}

function render() { renderTabs(); renderList(); }

function bind() {
  $("#list").addEventListener("click", async (e) => {
    const star = e.target.closest("button[data-save]");
    if (star) { toggleSave(star.dataset.save); return; }
    if (e.target.id === "copyClip") {
      const text = clippingText();
      try { await navigator.clipboard.writeText(text); e.target.textContent = "✅ 복사됨"; }
      catch { window.prompt("아래 내용을 복사하세요 (Ctrl+C)", text); }
      return;
    }
    if (e.target.id === "clearSaved" && window.confirm("저장한 기사를 모두 지울까요?")) {
      saved = {}; persistSaved(); render();
    }
  });
  $("#tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-t]");
    if (!b) return;
    state.topic = b.dataset.t; remember("topic", state.topic); render();
  });
  $("#countries").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-c]");
    if (!b) return;
    state.country = b.dataset.c; remember("country2", state.country); render();
  });
  document.querySelectorAll(".seg button").forEach((b) => {
    b.classList.toggle("on", b.dataset.sort === state.sort);
    b.addEventListener("click", () => {
      state.sort = b.dataset.sort; remember("sort2", state.sort);
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
    t = setTimeout(() => { state.q = e.target.value.trim(); render(); }, 150);
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
