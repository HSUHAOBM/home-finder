const DISTRICT_GROUPS_V7 = {
  "核心市區": ["新興區", "前金區", "苓雅區", "鹽埕區", "鼓山區", "三民區", "左營區", "前鎮區", "旗津區", "小港區"],
  "北高雄": ["楠梓區", "橋頭區", "岡山區", "梓官區", "彌陀區", "永安區", "茄萣區", "湖內區", "路竹區", "阿蓮區", "燕巢區", "田寮區"],
  "東南高雄": ["鳳山區", "仁武區", "鳥松區", "大社區", "大樹區", "大寮區", "林園區"],
  "旗美山區": ["旗山區", "美濃區", "六龜區", "甲仙區", "杉林區", "內門區", "茂林區", "桃源區", "那瑪夏區"],
};
const ORIGINAL_DISTRICTS_V7 = ["楠梓區", "三民區", "橋頭區", "大社區"];
const RESULT_STATUS_PRIORITY_V7 = [
  "exact_match",
  "acceptable",
  "needs_verification",
  "near_match",
  "rejected",
];
const RESULT_VIEW_MODE_KEY_V7 = "home-finder-result-view-mode";

function storedResultViewModeV7() {
  try {
    return localStorage.getItem(RESULT_VIEW_MODE_KEY_V7) === "compact"
      ? "compact"
      : "comfortable";
  } catch {
    return "comfortable";
  }
}

state.resultViewMode = storedResultViewModeV7();

function selectFirstNonEmptyStatusV7() {
  if (!state.payload || profileItems(state.activeProfile, state.activeStatus).length) return;
  const nextStatus = RESULT_STATUS_PRIORITY_V7.find(
    (status) => profileItems(state.activeProfile, status).length
  );
  if (!nextStatus || nextStatus === state.activeStatus) return;
  state.activeStatus = nextStatus;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.status === nextStatus);
  });
}

const districtOptionsV7 = document.querySelector(".district-options");
districtOptionsV7.outerHTML = `
  <div class="district-picker">
    <div class="district-picker-actions">
      <button id="district-original" type="button">原本四區</button>
      <button id="district-all" type="button">全選高雄38區</button>
      <button id="district-clear" type="button">清除</button>
      <span id="district-selected-count">已選 4 區</span>
    </div>
    <div class="district-groups">
      ${Object.entries(DISTRICT_GROUPS_V7).map(([group, districts]) => `
        <fieldset><legend>${group}</legend>
          <div>${districts.map((district) => `<label><input type="checkbox" name="district" value="${district}">${district}</label>`).join("")}</div>
        </fieldset>`).join("")}
    </div>
  </div>`;

function setDistrictsV7(districts) {
  document.querySelectorAll('input[name="district"]').forEach((input) => {
    input.checked = districts.includes(input.value);
  });
  updateDistrictCountV7();
}
function updateDistrictCountV7() {
  const count = document.querySelectorAll('input[name="district"]:checked').length;
  document.querySelector("#district-selected-count").textContent = `已選 ${count} 區`;
}
document.querySelector("#district-original").addEventListener("click", () => setDistrictsV7(ORIGINAL_DISTRICTS_V7));
document.querySelector("#district-all").addEventListener("click", () => setDistrictsV7(Object.values(DISTRICT_GROUPS_V7).flat()));
document.querySelector("#district-clear").addEventListener("click", () => setDistrictsV7([]));
document.querySelectorAll('input[name="district"]').forEach((input) => input.addEventListener("change", updateDistrictCountV7));

const previousFillSettingsFormV7 = fillSettingsForm;
fillSettingsForm = function fillSettingsFormV7() {
  previousFillSettingsFormV7();
  updateDistrictCountV7();
};

const previousListingCardV7 = listingCard;
listingCard = function listingCardV7(item) {
  let html = previousListingCardV7(item);
  const metric = item.metric_value === null || item.metric_value === undefined
    ? escapeHtml(item.metric_label || "未通過必要條件")
    : `${escapeHtml(item.metric_label)} ${number(item.metric_value)}%`;
  html = html.replace(/<span class="score">.*?<\/span>/, `<span class="score metric-${escapeHtml(item.status)}">${metric}</span>`);
  return html;
};

document.querySelector("#results").insertAdjacentHTML(
  "beforebegin",
  `<section class="result-toolbar" aria-label="房源排序與篩選">
    <div class="result-sort-control">
      <span>排序</span>
      <select id="result-sort" hidden aria-hidden="true">
        <option value="metric">理想條件符合度</option>
        <option value="failures">\u4e0d\u7b26\u5408\u9805\u76ee\uff08\u5c11\u5230\u591a\uff09</option>
        <option value="newest">最新發現</option>
        <option value="price">價格低到高</option>
        <option value="total-unit-asc">權狀單價低到高</option>
        <option value="total-unit-desc">權狀單價高到低</option>
        <option value="main-unit-asc">主建單價低到高</option>
        <option value="main-unit-desc">主建單價高到低</option>
        <option value="age-asc">屋齡新到舊</option>
        <option value="age-desc">屋齡舊到新</option>
        <option value="floor">樓層比例高到低</option>
      </select>
      <div class="sort-buttons" role="group" aria-label="房源排序方式">
        <button type="button" data-sort-field="failures" class="failure-sort-button">不符合項目</button>
        <button type="button" data-sort-field="price">總價</button>
        <button type="button" data-sort-field="total-unit">權狀單價</button>
        <button type="button" data-sort-field="main-unit">室內單價</button>
        <button type="button" data-sort-field="age">屋齡</button>
        <button type="button" data-sort-field="newest">最新</button>
    </div>
      </div>
    <label>行政區
      <select id="result-district"><option value="">全部已選地區</option></select>
    </label>
    <label class="toolbar-check"><input id="only-new" type="checkbox">只看本次新增／更新</label>
    <div class="result-view-control">
      <span>顯示</span>
      <div class="view-mode-buttons" role="group" aria-label="卡片顯示密度">
        <button type="button" data-view-mode="comfortable">完整</button>
        <button type="button" data-view-mode="compact">精簡</button>
      </div>
    </div>
    <span id="visible-result-count"></span>
    <div id="near-failure-filters" class="near-failure-filters" hidden>
      <span>\u4f9d\u4e0d\u7b26\u5408\u9805\u76ee</span><div id="near-failure-filter-buttons"></div>
    </div>
  </section>`
);
state.nearFailureFilter = "";
state.resultSort = { field: "newest", direction: "desc" };
const SORT_DEFAULT_DIRECTIONS_V7 = {
  metric: "desc", price: "asc", "total-unit": "asc", "main-unit": "asc",
  age: "asc", newest: "desc", failures: "asc",
};
const SORT_DIRECTION_LABELS_V7 = {
  metric: { asc: "符合度低到高", desc: "符合度高到低" },
  price: { asc: "總價低到高", desc: "總價高到低" },
  "total-unit": { asc: "權狀單價低到高", desc: "權狀單價高到低" },
  "main-unit": { asc: "室內單價低到高", desc: "室內單價高到低" },
  age: { asc: "屋齡新到舊", desc: "屋齡舊到新" },
  newest: { asc: "首次發現舊到新", desc: "首次發現新到舊" },
  failures: { asc: "不符合項目少到多", desc: "不符合項目多到少" },
};

function sortModeV7(field, direction) {
  if (field === "metric" && direction === "desc") return "metric";
  if (field === "newest" && direction === "desc") return "newest";
  if (field === "failures" && direction === "asc") return "failures";
  return `${field}-${direction}`;
}

function syncSortButtonsV7() {
  document.querySelectorAll("[data-sort-field]").forEach((button) => {
    const active = button.dataset.sortField === state.resultSort.field;
    const direction = active ? state.resultSort.direction : null;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
    const label = button.textContent.replace(/[↑↓]\s*$/, "").trim();
    button.textContent = `${label}${active ? (direction === "asc" ? " ↑" : " ↓") : ""}`;
    button.setAttribute("aria-label", active
      ? SORT_DIRECTION_LABELS_V7[button.dataset.sortField][direction]
      : `依${label}排序`);
  });
  const mode = sortModeV7(state.resultSort.field, state.resultSort.direction);
  const select = document.querySelector("#result-sort");
  if (![...select.options].some((option) => option.value === mode)) {
    select.insertAdjacentHTML("beforeend", `<option value="${mode}">${mode}</option>`);
  }
  select.value = mode;
}

document.querySelector(".sort-buttons").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-sort-field]");
  if (!button) return;
  const field = button.dataset.sortField;
  state.resultSort = state.resultSort.field === field
    ? { field, direction: state.resultSort.direction === "asc" ? "desc" : "asc" }
    : { field, direction: SORT_DEFAULT_DIRECTIONS_V7[field] };
  syncSortButtonsV7();
  renderResults();
});
syncSortButtonsV7();

function setResultViewModeV7(mode, persist = true) {
  const selected = mode === "compact" ? "compact" : "comfortable";
  state.resultViewMode = selected;
  document.querySelector("#results").classList.toggle("compact-view", selected === "compact");
  document.querySelectorAll("[data-view-mode]").forEach((button) => {
    const active = button.dataset.viewMode === selected;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  if (!persist) return;
  try { localStorage.setItem(RESULT_VIEW_MODE_KEY_V7, selected); } catch {}
}

document.querySelectorAll("[data-view-mode]").forEach((button) => {
  button.addEventListener("click", () => setResultViewModeV7(button.dataset.viewMode));
});
setResultViewModeV7(state.resultViewMode, false);

function failureCategoryV7(reason) {
  const text = String(reason || "");
  if (/\u7e3d\u50f9|\u50f9\u683c/.test(text)) return "\u7e3d\u50f9";
  if (/無汽車位|完全沒車位|無車位|車位[^，；：]*為無/.test(text)) return "無車位";
  if (/不是平面車位|非平面車位|機械車位|機械式|機械上層|機械下層/.test(text)) return "非平面車位";
  if (/\u8eca\u4f4d|\u6c7d\u8eca\u4f4d/.test(text)) return "\u8eca\u4f4d";
  if (/\u4e3b\u5efa\u7269|\u92b7\u552e\u576a\u6578|\u576a\u6578|\u576a\u9580\u6abb/.test(text)) return "\u576a\u6578";
  if (/\u6a13\u5c64|\u4f4d\u65bc.*\u6a13|\u5168\u68df/.test(text)) return "\u6a13\u5c64";
  if (/\u623f\u6578|\u623f\u9593|\d+\u623f/.test(text)) return "\u623f\u6578";
  if (/\u885b\u6d74|\u6d74\u5ba4|\d+\u885b/.test(text)) return "\u885b\u6d74";
  if (/\u5c4b\u9f61|\u5c4b\u6cc1|\u5e74/.test(text)) return "\u5c4b\u9f61";
  if (/\u578b\u614b|\u9810\u552e\u5c4b|\u4e2d\u53e4\u5c4b|\u900f\u5929|\u516c\u5bd3|\u83ef\u5ec8|\u5927\u6a13/.test(text)) return "\u7269\u4ef6\u985e\u578b";
  if (/\u82b1\u5712|\u5ead\u9662/.test(text)) return "\u5ead\u9662";
  return "\u5176\u4ed6";
}

function failureCategoriesV7(item) {
  return [...new Set((item.failures || []).map(failureCategoryV7))];
}

function renderNearFailureFiltersV7(items) {
  const box = document.querySelector("#near-failure-filters");
  box.hidden = !["near_match", "rejected"].includes(state.activeStatus);
  if (box.hidden) return;
  const counts = new Map();
  items.forEach((item) => failureCategoriesV7(item).forEach((category) => counts.set(category, (counts.get(category) || 0) + 1)));
  if (state.nearFailureFilter && !counts.has(state.nearFailureFilter)) state.nearFailureFilter = "";
  const buttons = [["", "\u5168\u90e8", items.length], ...[...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-TW")).map(([category, count]) => [category, category, count])];
  document.querySelector("#near-failure-filter-buttons").innerHTML = buttons.map(([value, label, count]) => `<button type="button" data-failure-category="${escapeHtml(value)}" class="${state.nearFailureFilter === value ? "active" : ""}">${escapeHtml(label)} <b>${count}</b></button>`).join("");
}


function sortItemsV7(items) {
  const mode = document.querySelector("#result-sort").value;
  const copy = [...items];
  const numericSort = (field, descending = false) => copy.sort((a, b) => {
    const first = Number(a[field]);
    const second = Number(b[field]);
    const firstMissing = !Number.isFinite(first) || first <= 0;
    const secondMissing = !Number.isFinite(second) || second <= 0;
    if (firstMissing !== secondMissing) return firstMissing ? 1 : -1;
    if (firstMissing) return (a.price || 999999) - (b.price || 999999);
    return descending ? second - first : first - second;
  });

  if (mode === "failures" || mode === "failures-asc") return copy.sort((a, b) => (a.failures || []).length - (b.failures || []).length || failureCategoriesV7(a).join("\u3001").localeCompare(failureCategoriesV7(b).join("\u3001"), "zh-TW") || (b.metric_value || 0) - (a.metric_value || 0));
  if (mode === "failures-desc") return copy.sort((a, b) => (b.failures || []).length - (a.failures || []).length || (b.metric_value || 0) - (a.metric_value || 0));
  if (mode === "price" || mode === "price-asc") return numericSort("price");
  if (mode === "price-desc") return numericSort("price", true);
  if (mode === "total-unit-asc") return numericSort("price_per_total_area");
  if (mode === "total-unit-desc") return numericSort("price_per_total_area", true);
  if (mode === "main-unit-asc") return numericSort("price_per_main_area");
  if (mode === "main-unit-desc") return numericSort("price_per_main_area", true);
  if (mode === "age-asc") return numericSort("age");
  if (mode === "age-desc") return numericSort("age", true);
  if (mode === "floor") return copy.sort((a, b) => ((b.floor || 0) / (b.total_floors || 999)) - ((a.floor || 0) / (a.total_floors || 999)));
  if (mode === "newest") return copy.sort((a, b) => String(b.first_seen_at || "").localeCompare(String(a.first_seen_at || "")));
  if (mode === "newest-asc") return copy.sort((a, b) => String(a.first_seen_at || "").localeCompare(String(b.first_seen_at || "")));
  if (mode === "metric-asc") return copy.sort((a, b) => (a.metric_value || 0) - (b.metric_value || 0) || (a.price || 999999) - (b.price || 999999));
  return copy.sort((a, b) => (b.metric_value || 0) - (a.metric_value || 0) || (a.price || 999999) - (b.price || 999999));
}

renderResults = function renderResultsV7() {
  if (!state.payload) {
    document.querySelector("#results").innerHTML = emptyState("正在讀取", "稍等一下，馬上整理結果。");
    return;
  }
  const district = document.querySelector("#result-district").value;
  const onlyNew = document.querySelector("#only-new").checked;
  let availableItems = profileItems(state.activeProfile, state.activeStatus);
  if (district) availableItems = availableItems.filter((item) => item.district === district);
  if (onlyNew) availableItems = availableItems.filter((item) => ["new", "updated"].includes(item.lifecycle_status) && !isTrackingStale(item));
  renderNearFailureFiltersV7(availableItems);
  let items = ["near_match", "rejected"].includes(state.activeStatus) && state.nearFailureFilter
    ? availableItems.filter((item) => failureCategoriesV7(item).includes(state.nearFailureFilter))
    : availableItems;
  items = sortItemsV7(items);
  document.querySelector("#visible-result-count").textContent = `顯示 ${items.length} 組`;
  if (!items.length) {
    document.querySelector("#results").innerHTML = emptyState("目前沒有房源", "請切換分類、行政區或取消「只看本次新增」。");
    return;
  }
  const activeItems = items.filter((item) => listingAvailabilityState(item) !== "removed");
  const removedItems = items.filter((item) => listingAvailabilityState(item) === "removed");
  const categoryItems = profileItems(state.activeProfile, state.activeStatus);
  const categoryClearHtml = state.activeStatus === "near_match"
    ? `<div class="category-clear-bar"><span>差強人意共 ${categoryItems.length} 筆</span><button type="button" class="clear-current-category">全部清除</button></div>`
    : "";
  const activeHtml = activeItems.length
    ? `<div class="availability-section-title"><strong>刊登中／尚未確認</strong><span>${activeItems.length} 筆</span></div>${activeItems.map(listingCard).join("")}`
    : "";
  const removedHtml = removedItems.length
    ? `<div class="availability-divider"><span>以下為已下架房源・${removedItems.length} 筆</span><button type="button" class="clear-removed-page">一鍵清除此頁已下架</button></div>${removedItems.map(listingCard).join("")}`
    : "";
  document.querySelector("#results").innerHTML = categoryClearHtml + activeHtml + removedHtml;
};

const previousRenderInsightV7 = renderInsight;
renderInsight = function renderInsightV7() {
  previousRenderInsightV7();
  const box = document.querySelector("#goal-insight");
  const diagnostic = state.payload && state.payload.search_diagnostics
    ? state.payload.search_diagnostics[state.activeProfile]
    : null;
  if (!box || !diagnostic) return;
  const successfulCrawl = state.payload.successful_crawls_by_profile
    ? state.payload.successful_crawls_by_profile[state.activeProfile]
    : null;
  const successTime = successfulCrawl ? new Date(successfulCrawl.finished_at).toLocaleString("zh-TW") : "尚無成功紀錄";
  const mode = diagnostic.mode === "full" ? "完整盤點" : "每日更新";
  const duration = formatDuration(diagnostic.duration_seconds);
  box.insertAdjacentHTML("beforeend", `
    <div class="coverage-summary">
      <span>上次搜尋覆蓋</span>
      <strong>${mode}・${diagnostic.district_count} 區${diagnostic.pages_requested ? `・${diagnostic.pages_requested} 頁` : ""}</strong>
      <small>最近成功 ${successTime}・讀取 ${diagnostic.fetched} 筆${duration ? `・耗時 ${duration}` : ""}・快取${diagnostic.cache_expired ? "已過期重讀" : "仍有效"}${diagnostic.detail_failures ? `・詳情失敗 ${diagnostic.detail_failures}` : ""}</small>
    </div>`);
};

const previousRenderNavigationV7 = renderNavigation;
renderNavigation = function renderNavigationV7() {
  selectFirstNonEmptyStatusV7();
  previousRenderNavigationV7();
  if (!state.settings) return;
  const select = document.querySelector("#result-district");
  const current = select.value;
  select.innerHTML = '<option value="">全部已選地區</option>' +
    state.settings.districts.map((district) => `<option value="${district}">${district}</option>`).join("");
  if (state.settings.districts.includes(current)) select.value = current;
};

["#result-sort", "#result-district", "#only-new"].forEach((selector) => {
  document.querySelector(selector).addEventListener("change", renderResults);
});
document.querySelector("#near-failure-filter-buttons").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-failure-category]");
  if (!button) return;
  state.nearFailureFilter = button.dataset.failureCategory;
  renderResults();
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    if (tab.dataset.status === "near_match") {
      state.nearFailureFilter = "";
      state.resultSort = { field: "failures", direction: "asc" };
    } else if (state.resultSort.field === "failures") {
      state.resultSort = { field: "newest", direction: "desc" };
    }
    syncSortButtonsV7();
    renderResults();
  });
});
