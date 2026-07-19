const state = {
  activeTab: "qualified",
  payload: null,
  lastFinishedAt: null,
};

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function number(value, suffix = "") {
  if (value === null || value === undefined || value === "") return "待確認";
  return `${Number(value).toLocaleString("zh-TW", { maximumFractionDigits: 3 })}${suffix}`;
}

function floorText(item) {
  if (item.floor === null || item.floor === undefined) return "待確認";
  return item.total_floors ? `${item.floor}/${item.total_floors} 樓` : `${item.floor} 樓`;
}

function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch {
    return "#";
  }
}

function noteItems(item) {
  const notes = [];
  item.strengths.slice(0, 2).forEach((text) => notes.push(`<li>${escapeHtml(text)}</li>`));
  item.questions.slice(0, 3).forEach((text) => notes.push(`<li class="question">必問：${escapeHtml(text)}</li>`));
  item.concerns.slice(0, 3).forEach((text) => notes.push(`<li class="concern">${escapeHtml(text)}</li>`));
  if (item.duplicates.length) {
    notes.push(`<li class="concern">疑似重複刊登：${escapeHtml(item.duplicates.join("、"))}</li>`);
  }
  return notes.join("");
}

function listingCard(item) {
  const label = item.status === "qualified" ? "直接符合" : "待確認";
  const price = item.price ? `${number(item.price)} 萬` : "總價待確認";
  return `
    <article class="listing-card">
      <div class="card-top">
        <span class="badge ${escapeHtml(item.status)}">${label}</span>
        <span class="score">適合度 ${number(item.score)} 分</span>
      </div>
      <h2>${escapeHtml(item.title)}</h2>
      <div class="price-row">
        <span class="price">${price}</span>
        <span class="district">${escapeHtml(item.district)}</span>
      </div>
      <div class="facts">
        <div class="fact"><span>主建物</span><strong>${number(item.main_area, " 坪")}</strong></div>
        <div class="fact"><span>格局</span><strong>${number(item.rooms, " 房")}・${number(item.baths, " 衛")}</strong></div>
        <div class="fact"><span>樓層</span><strong>${floorText(item)}</strong></div>
        <div class="fact"><span>屋齡</span><strong>${number(item.age, " 年")}</strong></div>
        <div class="fact"><span>車位</span><strong>${escapeHtml(item.parking || "待確認")}</strong></div>
        <div class="fact"><span>類型</span><strong>${escapeHtml(item.profile)}</strong></div>
      </div>
      <ul class="notes">${noteItems(item)}</ul>
      <a class="listing-link" href="${safeUrl(item.url)}" target="_blank" rel="noopener noreferrer">在 591 查看房源</a>
    </article>`;
}

function renderResults() {
  const container = $("#results");
  if (!state.payload) {
    container.innerHTML = '<div class="empty-state"><h2>正在讀取</h2><p>稍等一下，馬上整理現有結果。</p></div>';
    return;
  }

  if (state.activeTab === "rejected") {
    const reasons = state.payload.rejection_reasons || [];
    container.innerHTML = `
      <div class="reason-panel">
        <h2>為什麼這些房源被排除？</h2>
        <p>已排除 ${state.payload.summary.rejected} 筆，不混進候選清單。</p>
        <ul class="reason-list">
          ${reasons.length ? reasons.map((item) => `<li><span>${escapeHtml(item.reason)}</span><strong>${item.count} 筆</strong></li>`).join("") : "<li>目前沒有排除原因。</li>"}
        </ul>
      </div>`;
    return;
  }

  const items = state.payload.groups[state.activeTab] || [];
  if (!items.length) {
    const copy = state.activeTab === "qualified"
      ? ["目前沒有完全符合的房源", "可以重新搜尋；待確認分頁也可能有值得詢問的預售案。"]
      : ["目前沒有待確認房源", "資料完整而且符合的房源會出現在直接符合。"];
    container.innerHTML = `<div class="empty-state"><h2>${copy[0]}</h2><p>${copy[1]}</p></div>`;
    return;
  }
  container.innerHTML = items.map(listingCard).join("");
}

function renderSummary(payload) {
  const summary = payload.summary;
  $("#count-total").textContent = summary.total;
  $("#count-qualified").textContent = summary.qualified;
  $("#count-pending").textContent = summary.needs_verification;
  $("#count-rejected").textContent = summary.rejected;
  $("#tab-qualified").textContent = summary.qualified;
  $("#tab-pending").textContent = summary.needs_verification;
  $("#tab-rejected").textContent = summary.rejected;
  $("#updated-at").textContent = payload.updated_at
    ? `結果更新：${new Date(payload.updated_at).toLocaleString("zh-TW")}`
    : "還沒有搜尋紀錄";
}

async function loadResults() {
  try {
    const response = await fetch("/api/results", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "讀取失敗");
    state.payload = payload;
    renderSummary(payload);
    renderResults();
  } catch (error) {
    $("#results").innerHTML = `<div class="error-box">${escapeHtml(error.message)}</div>`;
  }
}

function renderStatus(status) {
  const button = $("#search-button");
  const light = $("#status-light");
  button.disabled = status.running;
  button.classList.toggle("running", status.running);
  $("#search-label").textContent = status.running ? "搜尋進行中" : "開始重新搜尋";
  $("#status-message").textContent = status.error
    ? `${status.message}：${status.error}`
    : status.message;
  light.className = `status-light ${status.running ? "running" : status.phase}`;
}

async function pollStatus() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    const status = await response.json();
    renderStatus(status);
    if (!status.running && status.finished_at && status.finished_at !== state.lastFinishedAt) {
      state.lastFinishedAt = status.finished_at;
      await loadResults();
    }
  } catch {
    $("#status-message").textContent = "暫時無法連接本機介面";
  }
}

async function startSearch() {
  const button = $("#search-button");
  button.disabled = true;
  try {
    const response = await fetch("/api/search", { method: "POST" });
    const status = await response.json();
    renderStatus(status);
  } catch (error) {
    $("#status-message").textContent = `無法開始：${error.message}`;
    button.disabled = false;
  }
}

$("#search-button").addEventListener("click", startSearch);
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    state.activeTab = tab.dataset.tab;
    renderResults();
  });
});

loadResults();
pollStatus();
setInterval(pollStatus, 1800);
