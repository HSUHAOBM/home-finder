const PROFILES = {
  "大樓公寓華廈": {
    number: "目標 01",
    title: "大樓・公寓・華廈",
    description: "必要：平面汽車位、主建物至少 15 坪、至少 2 房。高樓、頂樓、2 衛與屋齡 30 年內加分。",
  },
  "透天別墅": {
    number: "目標 02",
    title: "透天・車墅",
    description: "必要：總價 1,200 萬內且可停汽車。屋齡 30 年內優先，有花園、庭院再加分。",
  },
  "預售屋": {
    number: "目標 03",
    title: "預售屋",
    description: "必要：平面車位、至少 2 房、室內至少 15 坪。戶別總價、主建物與可購平車不明時列為待確認。",
  },
};

const state = {
  activeProfile: "大樓公寓華廈",
  activeStatus: "qualified",
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

function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch {
    return "#";
  }
}

function profileItems(profile, status) {
  if (!state.payload) return [];
  return (state.payload.groups[status] || []).filter((item) => item.profile === profile);
}

function profileCounts(profile) {
  return {
    qualified: profileItems(profile, "qualified").length,
    pending: profileItems(profile, "needs_verification").length,
    rejected: profileItems(profile, "rejected").length,
  };
}

function floorText(item) {
  if (item.floor === null || item.floor === undefined) return "待確認";
  return item.total_floors ? `${item.floor}/${item.total_floors} 樓` : `${item.floor} 樓`;
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
      <div class="price-row"><span class="price">${price}</span><span class="district">${escapeHtml(item.district)}</span></div>
      <div class="facts">
        <div class="fact"><span>主建物</span><strong>${number(item.main_area, " 坪")}</strong></div>
        <div class="fact"><span>格局</span><strong>${number(item.rooms, " 房")}・${number(item.baths, " 衛")}</strong></div>
        <div class="fact"><span>樓層</span><strong>${floorText(item)}</strong></div>
        <div class="fact"><span>屋齡</span><strong>${number(item.age, " 年")}</strong></div>
        <div class="fact"><span>車位</span><strong>${escapeHtml(item.parking || "待確認")}</strong></div>
        <div class="fact"><span>目標</span><strong>${escapeHtml(PROFILES[item.profile]?.title || item.profile)}</strong></div>
      </div>
      <ul class="notes">${noteItems(item)}</ul>
      <a class="listing-link" href="${safeUrl(item.url)}" target="_blank" rel="noopener noreferrer">在 591 查看房源</a>
    </article>`;
}

function renderRejected(items) {
  if (!items.length) return emptyState("目前沒有排除項目", "這一類尚未抓到被排除的房源。");
  const reasons = new Map();
  items.forEach((item) => {
    (item.failures.length ? item.failures : ["未符合此目標的必要條件"]).forEach((reason) => {
      reasons.set(reason, (reasons.get(reason) || 0) + 1);
    });
  });
  return `
    <div class="reason-panel">
      <h2>${escapeHtml(PROFILES[state.activeProfile].title)}的排除原因</h2>
      <p>這裡只統計目前購屋目標，不混入另外兩種房型。</p>
      <ul class="reason-list">
        ${[...reasons.entries()].sort((a, b) => b[1] - a[1]).map(([reason, count]) => `<li><span>${escapeHtml(reason)}</span><strong>${count} 筆</strong></li>`).join("")}
      </ul>
    </div>`;
}

function emptyState(title, text) {
  return `<div class="empty-state"><h2>${escapeHtml(title)}</h2><p>${escapeHtml(text)}</p></div>`;
}

function renderResults() {
  const container = $("#results");
  if (!state.payload) {
    container.innerHTML = emptyState("正在讀取", "稍等一下，馬上依三種目標分開整理。");
    return;
  }
  const items = profileItems(state.activeProfile, state.activeStatus);
  if (state.activeStatus === "rejected") {
    container.innerHTML = renderRejected(items);
    return;
  }
  if (!items.length) {
    const isQualified = state.activeStatus === "qualified";
    container.innerHTML = emptyState(
      isQualified ? "目前沒有完全符合的房源" : "目前沒有待確認房源",
      isQualified ? "可查看同一目標的待確認清單，或稍後重新搜尋。" : "有新房源時會自動歸到這個購屋目標。"
    );
    return;
  }
  container.innerHTML = items.map(listingCard).join("");
}

function renderGoalNavigation() {
  document.querySelectorAll(".goal-card").forEach((card) => {
    const profile = card.dataset.profile;
    const counts = profileCounts(profile);
    card.classList.toggle("active", profile === state.activeProfile);
    card.querySelector('[data-count="qualified"]').textContent = counts.qualified;
    card.querySelector('[data-count="pending"]').textContent = counts.pending;
    card.querySelector('[data-count="rejected"]').textContent = counts.rejected;
  });

  const profile = PROFILES[state.activeProfile];
  const counts = profileCounts(state.activeProfile);
  $("#active-goal-number").textContent = profile.number;
  $("#active-goal-title").textContent = profile.title;
  $("#active-goal-description").textContent = profile.description;
  $("#active-goal-total").textContent = `${counts.qualified + counts.pending + counts.rejected} 筆房源`;
  $("#tab-qualified").textContent = counts.qualified;
  $("#tab-pending").textContent = counts.pending;
  $("#tab-rejected").textContent = counts.rejected;
}

async function loadResults() {
  try {
    const response = await fetch("/api/results", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "讀取失敗");
    state.payload = payload;
    $("#updated-at").textContent = payload.updated_at
      ? `結果更新：${new Date(payload.updated_at).toLocaleString("zh-TW")}`
      : "還沒有搜尋紀錄";
    renderGoalNavigation();
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
  $("#status-message").textContent = status.error ? `${status.message}：${status.error}` : status.message;
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
  $("#search-button").disabled = true;
  try {
    const response = await fetch("/api/search", { method: "POST" });
    renderStatus(await response.json());
  } catch (error) {
    $("#status-message").textContent = `無法開始：${error.message}`;
    $("#search-button").disabled = false;
  }
}

$("#search-button").addEventListener("click", startSearch);
document.querySelectorAll(".goal-card").forEach((card) => {
  card.addEventListener("click", () => {
    state.activeProfile = card.dataset.profile;
    renderGoalNavigation();
    renderResults();
  });
});
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    state.activeStatus = tab.dataset.status;
    renderResults();
  });
});

loadResults();
pollStatus();
setInterval(pollStatus, 1800);
