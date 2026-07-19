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
    <label>排序
      <select id="result-sort">
        <option value="metric">理想條件符合度</option>
        <option value="newest">最新發現</option>
        <option value="price">價格低到高</option>
        <option value="floor">樓層比例高到低</option>
      </select>
    </label>
    <label>行政區
      <select id="result-district"><option value="">全部已選地區</option></select>
    </label>
    <label class="toolbar-check"><input id="only-new" type="checkbox">只看本次新增／更新</label>
    <span id="visible-result-count"></span>
  </section>`
);

function sortItemsV7(items) {
  const mode = document.querySelector("#result-sort").value;
  const copy = [...items];
  if (mode === "price") return copy.sort((a, b) => (a.price || 999999) - (b.price || 999999));
  if (mode === "floor") return copy.sort((a, b) => ((b.floor || 0) / (b.total_floors || 999)) - ((a.floor || 0) / (a.total_floors || 999)));
  if (mode === "newest") return copy.sort((a, b) => String(b.first_seen_at || "").localeCompare(String(a.first_seen_at || "")));
  return copy.sort((a, b) => (b.metric_value || 0) - (a.metric_value || 0) || (a.price || 999999) - (b.price || 999999));
}

renderResults = function renderResultsV7() {
  if (!state.payload) {
    document.querySelector("#results").innerHTML = emptyState("正在讀取", "稍等一下，馬上整理結果。");
    return;
  }
  const district = document.querySelector("#result-district").value;
  const onlyNew = document.querySelector("#only-new").checked;
  let items = profileItems(state.activeProfile, state.activeStatus);
  if (district) items = items.filter((item) => item.district === district);
  if (onlyNew) items = items.filter((item) => ["new", "updated"].includes(item.lifecycle_status));
  items = sortItemsV7(items);
  document.querySelector("#visible-result-count").textContent = `顯示 ${items.length} 組`;
  document.querySelector("#results").innerHTML = items.length
    ? items.map(listingCard).join("")
    : emptyState("目前沒有房源", "請切換分類、行政區或取消「只看本次新增」。");
};

const previousRenderInsightV7 = renderInsight;
renderInsight = function renderInsightV7() {
  previousRenderInsightV7();
  const box = document.querySelector("#goal-insight");
  const diagnostic = state.payload && state.payload.search_diagnostics
    ? state.payload.search_diagnostics[state.activeProfile]
    : null;
  if (!box || !diagnostic) return;
  const mode = diagnostic.mode === "full" ? "完整盤點" : "每日更新";
  box.insertAdjacentHTML("beforeend", `
    <div class="coverage-summary">
      <span>上次搜尋覆蓋</span>
      <strong>${mode}・${diagnostic.district_count} 區${diagnostic.pages_requested ? `・${diagnostic.pages_requested} 頁` : ""}</strong>
      <small>讀取 ${diagnostic.fetched} 筆・${diagnostic.duration_seconds} 秒・快取${diagnostic.cache_expired ? "已過期重讀" : "仍有效"}${diagnostic.detail_failures ? `・詳情失敗 ${diagnostic.detail_failures}` : ""}</small>
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
