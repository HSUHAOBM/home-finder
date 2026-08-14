const PROFILE_META = {
  "大樓公寓華廈": { number: "目標 01", title: "大樓・公寓・華廈" },
  "透天別墅": { number: "目標 02", title: "透天・車墅" },
  "預售屋": { number: "目標 03", title: "預售屋" },
};

const state = { activeProfile: "大樓公寓華廈", activeStatus: "qualified", payload: null, settings: null, settingsHistory: [], lastFinishedAt: null, statusPollTimer: null, searchRunning: false, serviceInstance: null };
const $ = (selector) => document.querySelector(selector);
const value = (id) => Number($(id).value);
const checked = (id) => $(id).checked;

function escapeHtml(input) {
  return String(input ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}
function number(input, suffix = "") {
  if (input === null || input === undefined || input === "") return "待確認";
  return `${Number(input).toLocaleString("zh-TW", { maximumFractionDigits: 3 })}${suffix}`;
}
function safeUrl(input) {
  try { const url = new URL(input); return ["http:", "https:"].includes(url.protocol) ? url.href : "#"; } catch { return "#"; }
}
function profileItems(profile, status) {
  return state.payload ? (state.payload.groups[status] || []).filter((item) => item.profile === profile) : [];
}
function profileCounts(profile) {
  return { qualified: profileItems(profile, "qualified").length, pending: profileItems(profile, "needs_verification").length, rejected: profileItems(profile, "rejected").length };
}
function floorText(item) {
  if (item.floor === null || item.floor === undefined) return "待確認";
  return item.total_floors ? `${item.floor}/${item.total_floors} 樓` : `${item.floor} 樓`;
}

function goalRule(profile) {
  if (!state.settings) return "正在讀取條件…";
  const config = state.settings.profiles[profile];
  if (profile === "透天別墅") return `${number(config.max_price)} 萬內・${config.require_parking ? "可停汽車必要" : "停車非必要"}・屋齡 ${number(config.preferred_max_age)} 年內優先`;
  return `${number(config.max_price)} 萬內・主建 ≥ ${number(config.min_main_area)} 坪・至少 ${number(config.min_rooms)} 房・${config.require_flat_parking ? "平面車位必要" : "車位非必要"}`;
}
function goalDescription(profile) {
  if (!state.settings) return "";
  const config = state.settings.profiles[profile];
  if (profile === "大樓公寓華廈") return `必要條件：總價不超過 ${number(config.max_price)} 萬、主建物至少 ${number(config.min_main_area)} 坪、至少 ${number(config.min_rooms)} 房${config.require_flat_parking ? "、平面車位" : ""}。理想總價 ${number(config.target_price)} 萬，偏好 ${number(config.preferred_min_baths)} 衛、屋齡 ${number(config.preferred_max_age)} 年內${config.prefer_high_floor ? "及高樓層" : ""}。`;
  if (profile === "透天別墅") return `必要條件：總價不超過 ${number(config.max_price)} 萬${config.require_parking ? "且可停汽車" : ""}。理想總價 ${number(config.target_price)} 萬，偏好屋齡 ${number(config.preferred_max_age)} 年內${config.prefer_garden ? "，花園或庭院加分" : ""}。`;
  return `必要條件：總價不超過 ${number(config.max_price)} 萬、室內／主建至少 ${number(config.min_main_area)} 坪、至少 ${number(config.min_rooms)} 房${config.require_flat_parking ? "、平面車位" : ""}。價格、主建物或戶別車位未公開時列待確認。`;
}

function noteItems(item) {
  const notes = [];
  item.strengths.slice(0, 2).forEach((text) => notes.push(`<li>${escapeHtml(text)}</li>`));
  item.questions.forEach((text) => notes.push(`<li class="question">必問：${escapeHtml(text)}</li>`));
  item.concerns.forEach((text) => notes.push(`<li class="concern">${escapeHtml(text)}</li>`));
  if (item.duplicates.length) notes.push(`<li class="concern">疑似重複刊登：${escapeHtml(item.duplicates.join("、"))}</li>`);
  return notes.join("");
}

function listingCard(item) {
  const labels = { qualified: "直接符合", needs_verification: "待確認", rejected: "已排除" };
  const price = item.price ? `${number(item.price)} 萬` : "總價待確認";
  const totalUnitPrice = number(item.price_per_total_area, " \u842c/\u576a");
  const mainUnitPrice = number(item.price_per_main_area, " \u842c/\u576a");
  const failureCount = item.failures.length;
  const failures = item.status === "rejected" ? `<div class="failure-box"><strong>不符合必要條件（${failureCount || "未確認"} 項）</strong><ul>${(failureCount ? item.failures : ["未符合必要條件"]).map((text) => `<li>${escapeHtml(text)}</li>`).join("")}</ul></div>` : "";
  return `<article class="listing-card status-${escapeHtml(item.status)} ${item.status === "rejected" ? "rejected-card" : ""}">
    <div class="card-top"><span class="badge ${escapeHtml(item.status)}">${labels[item.status]}</span><span class="score">適合度 ${number(item.score)} 分</span></div>
    <h2>${escapeHtml(item.title)}</h2><div class="price-row"><div class="price-summary"><span class="price">${price}</span><div class="unit-prices"><span class="unit-price" title="\u7e3d\u50f9 \u00f7 \u6b0a\u72c0\u7e3d\u576a\u6578\uff1b\u6b0a\u72c0\u576a\u6578\u901a\u5e38\u5305\u542b\u516c\u8a2d\uff0c\u4e5f\u53ef\u80fd\u5305\u542b\u8eca\u4f4d"><small>\u6b0a\u72c0\u55ae\u50f9</small><strong>${totalUnitPrice}</strong></span><span class="unit-price" title="\u7e3d\u50f9 \u00f7 \u4e3b\u5efa\u7269\u576a\u6578\uff1b\u7e3d\u50f9\u82e5\u5305\u542b\u8eca\u4f4d\uff0c\u8a08\u7b97\u7d50\u679c\u4e5f\u5305\u542b\u8eca\u4f4d\u50f9\u683c\u5f71\u97ff"><small>\u4e3b\u5efa\u55ae\u50f9</small><strong>${mainUnitPrice}</strong></span></div></div><span class="district">${escapeHtml(item.district)}</span></div>
    <div class="facts"><div class="fact"><span>主建物</span><strong>${number(item.main_area, " 坪")}</strong></div><div class="fact"><span>格局</span><strong>${number(item.rooms, " 房")}・${number(item.baths, " 衛")}</strong></div><div class="fact"><span>樓層</span><strong>${floorText(item)}</strong></div><div class="fact"><span>屋齡</span><strong>${number(item.age, " 年")}</strong></div><div class="fact"><span>車位</span><strong>${escapeHtml(item.parking || "待確認")}</strong></div><div class="fact"><span>591 編號</span><strong>${escapeHtml(item.id)}</strong></div></div>
    ${failures}<ul class="notes">${noteItems(item)}</ul><a class="listing-link" href="${safeUrl(item.url)}" target="_blank" rel="noopener noreferrer">開啟原始 591 房源</a></article>`;
}
function emptyState(title, text) { return `<div class="empty-state"><h2>${escapeHtml(title)}</h2><p>${escapeHtml(text)}</p></div>`; }

function renderResults() {
  if (!state.payload) { $("#results").innerHTML = emptyState("正在讀取", "稍等一下，馬上整理結果。"); return; }
  const items = profileItems(state.activeProfile, state.activeStatus);
  if (!items.length) {
    const text = state.activeStatus === "rejected" ? "目前沒有這個目標的排除房源。" : "可以查看同一目標的其他分類，或重新搜尋。";
    $("#results").innerHTML = emptyState("目前沒有房源", text); return;
  }
  $("#results").innerHTML = items.map(listingCard).join("");
}

function renderNavigation() {
  document.querySelectorAll(".goal-card").forEach((card) => {
    const profile = card.dataset.profile; const counts = profileCounts(profile);
    card.classList.toggle("active", profile === state.activeProfile);
    card.querySelector("[data-goal-rule]").textContent = goalRule(profile);
    card.querySelector('[data-count="qualified"]').textContent = counts.qualified;
    card.querySelector('[data-count="pending"]').textContent = counts.pending;
    card.querySelector('[data-count="rejected"]').textContent = counts.rejected;
  });
  const meta = PROFILE_META[state.activeProfile]; const counts = profileCounts(state.activeProfile);
  $("#active-goal-number").textContent = meta.number; $("#active-goal-title").textContent = meta.title; $("#active-goal-description").textContent = goalDescription(state.activeProfile);
  $("#active-goal-total").textContent = `${counts.qualified + counts.pending + counts.rejected} 筆房源`;
  $("#tab-qualified").textContent = counts.qualified; $("#tab-pending").textContent = counts.pending; $("#tab-rejected").textContent = counts.rejected;
  if (state.settings) $("#criteria-summary").innerHTML = state.settings.districts.map((district) => `<span>${escapeHtml(district)}</span>`).join("") + `<span>三種目標各自計算</span><span>條件可調整</span>`;
}

async function readJsonResponse(response, fallbackMessage) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    if (response.status >= 500) {
      throw new Error("本機服務版本可能已更新，請關閉舊的命令視窗，再重新開啟找房介面。");
    }
    throw new Error(fallbackMessage);
  }
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || payload.message || fallbackMessage);
  return payload;
}


async function loadResults() {
  const response = await fetch("/api/results", { cache: "no-store" });
  const payload = await readJsonResponse(response, "讀取結果失敗");
  state.payload = payload;
  const successfulCrawl = payload.last_successful_crawl;
  const mode = successfulCrawl && successfulCrawl.mode === "full" ? "完整盤點" : "每日更新";
  const duration = successfulCrawl ? formatDuration(successfulCrawl.duration_seconds) : null;
  $("#updated-at").textContent = successfulCrawl
    ? `最近成功爬蟲：${new Date(successfulCrawl.finished_at).toLocaleString("zh-TW")}・${successfulCrawl.profile}・${mode}・${successfulCrawl.fetched} 筆${duration ? `・耗時 ${duration}` : ""}`
    : "還沒有成功爬蟲紀錄";
  $("#updated-at").title = payload.updated_at
    ? `結果檔更新：${new Date(payload.updated_at).toLocaleString("zh-TW")}`
    : "還沒有結果檔";
}

function formatDuration(value) {
  if (value === null || value === undefined || value === "") return null;
  const totalSeconds = Math.max(0, Math.round(Number(value)));
  if (!Number.isFinite(totalSeconds)) return null;
  if (totalSeconds < 60) return `${totalSeconds} 秒`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return seconds ? `${minutes} 分 ${seconds} 秒` : `${minutes} 分`;
}
async function loadSettings() {
  const response = await fetch("/api/settings", { cache: "no-store" });
  const payload = await readJsonResponse(response, "讀取條件失敗");
  state.settings = payload;
}

function settingsHistoryLabel(entry) {
  const settings = entry.settings;
  const savedAt = new Date(entry.saved_at).toLocaleString("zh-TW");
  return `${savedAt}｜${settings.districts.length} 區｜大樓上限 ${settings.profiles["大樓公寓華廈"].max_price} 萬`;
}

function renderSettingsHistory() {
  const select = $("#settings-history-select");
  const button = $("#settings-history-load");
  if (!select || !button) return;
  select.innerHTML = '<option value="">選擇過去儲存的條件</option>' + state.settingsHistory.map((entry) => `<option value="${escapeHtml(entry.id)}">${escapeHtml(settingsHistoryLabel(entry))}</option>`).join("");
  button.disabled = state.settingsHistory.length === 0;
  $("#settings-history-help").textContent = state.settingsHistory.length
    ? `已保存 ${state.settingsHistory.length} 個版本；載入後請檢查，再按「儲存並套用」。`
    : "尚無歷史版本；下一次儲存時會同時保留修改前與修改後條件。";
}

async function loadSettingsHistory() {
  const response = await fetch("/api/settings/history", { cache: "no-store" });
  const payload = await readJsonResponse(response, "讀取條件歷史失敗");
  state.settingsHistory = payload.history || [];
  renderSettingsHistory();
}


function fillSettingsForm(settings = state.settings) {
  const s = settings; document.querySelectorAll('input[name="district"]').forEach((input) => { input.checked = s.districts.includes(input.value); });
  $("#resale-details").value = s.search.resale_details; $("#presale-details").value = s.search.presale_details;
  const c = s.profiles["大樓公寓華廈"]; $("#condo-max-price").value = c.max_price; $("#condo-target-price").value = c.target_price; $("#condo-min-area").value = c.min_main_area; $("#condo-min-rooms").value = c.min_rooms; $("#condo-min-baths").value = c.preferred_min_baths; $("#condo-max-age").value = c.preferred_max_age; $("#condo-flat-parking").checked = c.require_flat_parking; $("#condo-high-floor").checked = c.prefer_high_floor;
  const h = s.profiles["透天別墅"]; $("#house-max-price").value = h.max_price; $("#house-target-price").value = h.target_price; $("#house-max-age").value = h.preferred_max_age; $("#house-parking").checked = h.require_parking; $("#house-garden").checked = h.prefer_garden;
  const p = s.profiles["預售屋"]; $("#presale-max-price").value = p.max_price; $("#presale-target-price").value = p.target_price; $("#presale-min-area").value = p.min_main_area; $("#presale-min-rooms").value = p.min_rooms; $("#presale-min-baths").value = p.preferred_min_baths; $("#presale-flat-parking").checked = p.require_flat_parking;
  $("#settings-error").textContent = "";
}

function collectSettings() {
  return { districts: [...document.querySelectorAll('input[name="district"]:checked')].map((input) => input.value), search: { resale_details: value("#resale-details"), presale_details: value("#presale-details") }, profiles: {
    "大樓公寓華廈": { max_price: value("#condo-max-price"), target_price: value("#condo-target-price"), min_main_area: value("#condo-min-area"), min_rooms: value("#condo-min-rooms"), preferred_min_baths: value("#condo-min-baths"), preferred_max_age: value("#condo-max-age"), require_flat_parking: checked("#condo-flat-parking"), prefer_high_floor: checked("#condo-high-floor") },
    "透天別墅": { max_price: value("#house-max-price"), target_price: value("#house-target-price"), preferred_max_age: value("#house-max-age"), require_parking: checked("#house-parking"), prefer_garden: checked("#house-garden") },
    "預售屋": { max_price: value("#presale-max-price"), target_price: value("#presale-target-price"), min_main_area: value("#presale-min-area"), min_rooms: value("#presale-min-rooms"), preferred_min_baths: value("#presale-min-baths"), preferred_max_age: 5, require_flat_parking: checked("#presale-flat-parking") },
  }};
}

async function saveSettings(event) {
  event.preventDefault(); const button = $("#settings-save"); const originalLabel = button.textContent; button.disabled = true; button.textContent = "儲存中…"; $("#settings-error").textContent = "";
  try {
    const response = await fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(collectSettings()) });
    const payload = await readJsonResponse(response, "儲存失敗");
    state.settings = payload.settings; state.settingsHistory = payload.history || state.settingsHistory; state.payload = payload.results; renderSettingsHistory(); renderNavigation(); renderResults(); button.textContent = `已儲存 ${payload.settings.districts.length} 區 ✓`; await new Promise((resolve) => setTimeout(resolve, 650)); $("#settings-dialog").close(); $("#status-message").textContent = `條件已儲存 ${payload.settings.districts.length} 區，並套用到目前結果`;
  } catch (error) { $("#settings-error").textContent = error.message; } finally { button.disabled = false; button.textContent = originalLabel; }
}

function stopStatusPolling() {
  if (state.statusPollTimer !== null) clearTimeout(state.statusPollTimer);
  state.statusPollTimer = null;
}

function scheduleStatusPoll(delay = 2500) {
  stopStatusPolling();
  if (document.hidden || !state.searchRunning) return;
  state.statusPollTimer = setTimeout(() => {
    state.statusPollTimer = null;
    pollStatus();
  }, delay);
}

function renderStatus(status) {
  state.searchRunning = Boolean(status.running);
  const button = $("#search-button"); const light = $("#status-light"); button.disabled = status.running; button.classList.toggle("running", status.running); $("#settings-button").disabled = status.running;
  $("#search-label").textContent = status.running ? "搜尋進行中" : "開始重新搜尋";
  const elapsed = status.running && status.started_at
    ? formatDuration((Date.now() - new Date(status.started_at).getTime()) / 1000)
    : formatDuration(status.duration_seconds);
  const message = status.error ? `${status.message}：${status.error}` : status.message;
  $("#status-message").textContent = `${message}${elapsed ? `・${status.running ? "已執行" : "耗時"} ${elapsed}` : ""}`;
  light.className = `status-light ${status.running ? "running" : status.phase}`;
  if (state.searchRunning) scheduleStatusPoll(); else stopStatusPolling();
}
async function pollStatus() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" }); const status = await readJsonResponse(response, "讀取狀態失敗");
    if (state.serviceInstance && status.service_instance && status.service_instance !== state.serviceInstance) {
      window.location.reload(); return;
    }
    if (status.service_instance) state.serviceInstance = status.service_instance;
    renderStatus(status);
    if (!status.running && status.finished_at && status.finished_at !== state.lastFinishedAt) { state.lastFinishedAt = status.finished_at; await loadResults(); renderNavigation(); renderResults(); }
  } catch (error) { $("#status-message").textContent = error.message.includes("本機服務版本") ? error.message : "暫時無法連接本機介面"; if (state.searchRunning) scheduleStatusPoll(5000); }
}
async function startSearch() {
  $("#search-button").disabled = true; try { const response = await fetch("/api/search", { method: "POST" }); renderStatus(await readJsonResponse(response, "開始搜尋失敗")); } catch (error) { $("#status-message").textContent = `無法開始：${error.message}`; $("#search-button").disabled = false; }
}

$("#search-button").addEventListener("click", startSearch); $("#settings-button").addEventListener("click", () => { fillSettingsForm(); renderSettingsHistory(); $("#settings-dialog").showModal(); }); $("#settings-close").addEventListener("click", () => $("#settings-dialog").close()); $("#settings-cancel").addEventListener("click", () => $("#settings-dialog").close()); $("#settings-form").addEventListener("submit", saveSettings);
$("#settings-history-load").addEventListener("click", () => {
  const entry = state.settingsHistory.find((item) => item.id === $("#settings-history-select").value);
  if (!entry) { $("#settings-error").textContent = "請先選擇一個歷史版本"; return; }
  fillSettingsForm(entry.settings);
  $("#settings-error").textContent = `已載入 ${new Date(entry.saved_at).toLocaleString("zh-TW")} 的條件；確認後請按「儲存並套用」。`;
});
document.querySelectorAll(".goal-card").forEach((card) => card.addEventListener("click", () => { state.activeProfile = card.dataset.profile; renderNavigation(); renderResults(); }));
document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => { document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active")); tab.classList.add("active"); state.activeStatus = tab.dataset.status; renderResults(); }));

document.addEventListener("visibilitychange", () => { if (document.hidden) stopStatusPolling(); else pollStatus(); });
window.addEventListener("focus", () => { if (!document.hidden) pollStatus(); });

(async function init() { try { await Promise.all([loadSettings(), loadResults(), loadSettingsHistory()]); renderNavigation(); renderResults(); await pollStatus(); } catch (error) { $("#results").innerHTML = `<div class="error-box">${escapeHtml(error.message)}</div>`; } }());
