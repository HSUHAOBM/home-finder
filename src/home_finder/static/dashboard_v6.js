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
goalActionBarV6.insertAdjacentHTML(
  "afterbegin",
  `<label class="search-mode-control">搜尋範圍
    <select id="search-mode">
      <option value="daily">每日更新（近 3 天／3 頁）</option>
      <option value="days_7">近 7 天／每區 5 頁</option>
      <option value="days_10">近 10 天／每區 7 頁</option>
      <option value="days_15">近 15 天／每區 15 頁</option>
      <option value="full">完整盤點（近 30 天／10 頁）</option>
    </select>
  </label>`
);

const oldSearchButtonV6 = document.querySelector("#selected-search-button");
const cleanSearchButtonV6 = oldSearchButtonV6.cloneNode(true);
oldSearchButtonV6.replaceWith(cleanSearchButtonV6);

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
    document.querySelector('#search-mode option[value="daily"]').textContent =
      `每日更新（近 ${search.publish_days || "不限"} 天／${search.pages} 頁）`;
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
  if (status.running) {
    const modeLabels = {
      full: "完整盤點", days_7: "近 7 天／每區 5 頁",
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
