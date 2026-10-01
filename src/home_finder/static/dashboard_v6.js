state.activeStatus = "exact_match";

document.querySelectorAll(".goal-counts").forEach((counts) => {
  counts.innerHTML =
    '<b data-count="qualified">0</b> 完全符合・' +
    '<b data-count="acceptable">0</b> 可接受・' +
    '<b data-count="pending">0</b> 待確認・' +
    '<b data-count="rejected">0</b> 排除';
});

const exactTabV6 = document.querySelector('[data-status="qualified"]');
exactTabV6.dataset.status = "exact_match";
exactTabV6.innerHTML = '完全符合 <span id="tab-qualified">0</span>';
exactTabV6.insertAdjacentHTML(
  "afterend",
  '<button class="tab acceptable-tab" type="button" data-status="acceptable">可接受 <span id="tab-acceptable">0</span></button>'
);

const goalActionBarV6 = document.querySelector(".goal-action-bar");
goalActionBarV6.classList.add("search-command-panel");
document.querySelector(".active-goal").insertAdjacentElement("afterend", goalActionBarV6);
goalActionBarV6.insertAdjacentHTML(
  "afterbegin",
  `<div class="search-mode-control">
    <header class="search-mode-heading">
      <span class="section-label">SEARCH COVERAGE</span>
      <strong>這次要搜尋多大的範圍？</strong>
      <small>日常先找新房源；需要補漏時再擴大範圍或完整盤點。</small>
    </header>
    <input id="search-mode" type="hidden" value="daily">
    <div class="search-mode-buttons" role="group" aria-label="選擇搜尋範圍">
      <button type="button" class="search-mode-button active" data-search-mode="daily">
        <strong>每日找新房源</strong><small>近 5 天・每區 3 頁</small>
      </button>
      <button type="button" class="search-mode-button" data-search-mode="days_15">
        <strong>擴大搜尋</strong><small>近 15 天・每區 15 頁</small>
      </button>
      <button type="button" class="search-mode-button full-scan-button" data-search-mode="full">
        <strong>完整盤點現有房源</strong><small>不限刊登時間・建議每週執行</small>
      </button>
      <button type="button" class="search-mode-button full-scan-button" data-search-mode="all_details">
        <strong>目前分類｜全部詳情</strong><small>不限刊登時間・不限詳情筆數</small>
      </button>
    </div>
    <p id="search-mode-help" class="search-mode-help">快速找出最近刊登或更新的房源。</p>
  </div>`
);

const SEARCH_MODE_HELP_V6 = {
  daily: "快速找出最近刊登或更新的房源。",
  days_15: "補找近 15 天內可能被每日搜尋漏掉的房源。",
  full: "盤點所選行政區目前仍在 591 列表的房源，不限制刊登日期；滿頁時會依價格與房型拆分。",
  all_details: "只處理目前選取的分類，並逐筆讀取本輪找到的所有房源詳情。",
};

function selectSearchModeV6(mode) {
  const select = document.querySelector("#search-mode");
  select.value = mode;
  document.querySelectorAll("[data-search-mode]").forEach((button) => {
    const selected = button.dataset.searchMode === mode;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  document.querySelector("#search-mode-help").textContent = SEARCH_MODE_HELP_V6[mode] || "";
}

document.querySelectorAll("[data-search-mode]").forEach((button) => {
  button.addEventListener("click", () => selectSearchModeV6(button.dataset.searchMode));
});

const oldSearchButtonV6 = document.querySelector("#selected-search-button");
const cleanSearchButtonV6 = oldSearchButtonV6.cloneNode(true);
oldSearchButtonV6.replaceWith(cleanSearchButtonV6);

const oldAllProfilesButtonV6 = document.querySelector("#all-profiles-search-button");
const cleanAllProfilesButtonV6 = oldAllProfilesButtonV6.cloneNode(true);
oldAllProfilesButtonV6.replaceWith(cleanAllProfilesButtonV6);

function variantsHtmlV6(item) {
  if (!item.variants || item.variants.length <= 1) return "";
  const links = item.variants
    .map(
      (variant, index) =>
        `<a href="${safeUrl(variant.url)}" target="_blank" rel="noopener noreferrer">刊登 ${index + 1}・${escapeHtml(variant.price ? number(variant.price) + " 萬" : "價格待確認")}</a>`
    )
    .join("");
  return `<div class="variant-box"><strong>已將 ${item.variants.length} 筆高度相似刊登合併為同一組</strong><div>${links}</div></div>`;
}

const previousListingCardV6 = listingCard;
listingCard = function listingCardV6(item) {
  if (!["exact_match", "acceptable"].includes(item.status)) {
    return previousListingCardV6(item);
  }
  const html = previousListingCardV6({ ...item, status: "qualified" });
  const label = item.status === "exact_match" ? "完全符合" : "可接受";
  const gaps = item.ideal_gaps && item.ideal_gaps.length
    ? `<div class="ideal-gap-box"><strong>尚未達到理想目標</strong><ul>${item.ideal_gaps.map((gap) => `<li>${escapeHtml(gap)}</li>`).join("")}</ul></div>`
    : "";
  return html
    .replace("badge qualified", `badge ${item.status}`)
    .replace(">直接符合</span>", `>${label}</span>`)
    .replace('<a class="listing-link"', `${gaps}${variantsHtmlV6(item)}<a class="listing-link"`);
};

renderInsight = function renderInsightV6() {
  const box = document.querySelector("#goal-insight");
  if (!box || !state.payload) return;
  const insight = (state.payload.profile_insights || {})[state.activeProfile];
  if (!insight) {
    box.innerHTML = "";
    return;
  }
  const headline = insight.exact_match
    ? `找到 ${insight.exact_match} 組完全符合目標`
    : "目前尚未找到完全符合目標的房子";
  const secondary = [
    insight.acceptable ? `${insight.acceptable} 組可接受` : "",
    insight.needs_verification ? `${insight.needs_verification} 組待確認` : "",
    insight.near_match ? `${insight.near_match} 組差強人意（1～2 項必要條件不符）` : "",
  ].filter(Boolean).join("・") || "目前沒有接近的候選";
  const reasons = (insight.top_reasons || [])
    .map((item) => `<li><span>${escapeHtml(item.reason)}</span><b>${item.count} 組</b></li>`)
    .join("");
  box.innerHTML = `
    <div><strong>${headline}</strong><p>${secondary}</p>
      <small>${insight.source_listings} 筆刊登已整理為 ${insight.properties} 組房源</small>
    </div>
    ${reasons ? `<div class="reason-summary"><span>主要排除原因</span><ul>${reasons}</ul></div>` : ""}`;
};

const previousRenderNavigationV6 = renderNavigation;
renderNavigation = function renderNavigationV6() {
  previousRenderNavigationV6();
  if (state.settings) {
    const search = state.settings.search;
    const dailyDetail = document.querySelector('[data-search-mode="daily"] small');
    dailyDetail.textContent = state.activeProfile === "透天別墅"
      ? `不限刊登時間・每區 ${search.pages} 頁`
      : `近 ${search.publish_days || "不限"} 天・每區 ${search.pages} 頁`;
  }
  const insights = state.payload ? state.payload.profile_insights || {} : {};
  document.querySelectorAll(".goal-card").forEach((card) => {
    const insight = insights[card.dataset.profile];
    if (!insight) return;
    card.querySelector('[data-count="qualified"]').textContent = insight.exact_match;
    card.querySelector('[data-count="acceptable"]').textContent = insight.acceptable;
    card.querySelector('[data-count="pending"]').textContent = insight.needs_verification;
    card.querySelector('[data-count="rejected"]').textContent = insight.rejected;
  });
  const insight = insights[state.activeProfile];
  if (!insight) return;
  document.querySelector("#tab-qualified").textContent = insight.exact_match;
  document.querySelector("#tab-acceptable").textContent = insight.acceptable;
  document.querySelector("#tab-pending").textContent = insight.needs_verification;
  document.querySelector("#tab-near").textContent = insight.near_match;
  document.querySelector("#tab-rejected").textContent = insight.rejected;
  document.querySelector("#active-goal-total").textContent =
    `${insight.properties} 組房源（原始刊登 ${insight.source_listings} 筆）`;
  renderInsight();
};

const previousRenderStatusV6 = renderStatus;
renderStatus = function renderStatusV6(status) {
  previousRenderStatusV6(status);
  document.querySelector("#search-mode").disabled = status.running;
  document.querySelectorAll("[data-search-mode]").forEach((button) => {
    button.disabled = status.running;
  });
  document.querySelector("#all-profiles-search-button").disabled = status.running;
  if (status.running) {
    const modeLabels = {
      all_details: "目前分類全部詳情", full: "完整盤點", days_7: "近 7 天／每區 5 頁",
      days_10: "近 10 天／每區 7 頁",
      days_15: "近 15 天／每區 15 頁", daily: "每日更新",
    };
    const mode = modeLabels[status.search_mode] || "每日更新";
    document.querySelector("#selected-search-label").textContent = `正在${mode}`;
  }
};

async function startSelectedSearchV6() {
  const button = document.querySelector("#selected-search-button");
  const mode = document.querySelector("#search-mode").value;
  button.disabled = true;
  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: state.activeProfile, mode }),
    });
    const payload = await readJsonResponse(response, "無法開始搜尋");
    renderStatus(payload);
  } catch (error) {
    document.querySelector("#status-message").textContent = `無法開始：${error.message}`;
    button.disabled = false;
  }
}

document.querySelector('[data-status="acceptable"]').addEventListener("click", (event) => {
  document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
  event.currentTarget.classList.add("active");
  state.activeStatus = "acceptable";
  renderResults();
});
cleanSearchButtonV6.addEventListener("click", startSelectedSearchV6);

async function startAllProfilesSearchV6() {
  const button = document.querySelector("#all-profiles-search-button");
  const mode = document.querySelector("#search-mode").value;
  button.disabled = true;
  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "全部分類", mode }),
    });
    const payload = await readJsonResponse(response, "無法開始三類全部爬");
    renderStatus(payload);
  } catch (error) {
    document.querySelector("#status-message").textContent = `無法開始：${error.message}`;
    button.disabled = false;
  }
}

cleanAllProfilesButtonV6.addEventListener("click", startAllProfilesSearchV6);
