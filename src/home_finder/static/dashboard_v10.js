PROFILE_META["大樓公寓華廈"].title = "大樓・華廈";
document.querySelectorAll('.goal-card[data-profile="大樓公寓華廈"] strong')
  .forEach((element) => { element.textContent = "大樓・華廈"; });
document.querySelectorAll(".condo-settings .profile-heading h3")
  .forEach((element) => { element.textContent = "大樓・華廈"; });

const importPanelV10 = document.createElement("section");
importPanelV10.className = "listing-import-panel";
importPanelV10.innerHTML = `
  <div>
    <span class="section-label">DIRECT CHECK</span>
    <strong>貼上 591 房源網址立即查核</strong>
    <small>公寓會直接排除；總價最多讀到 1,300 萬。</small>
  </div>
  <form id="listing-import-form">
    <input id="listing-import-url" type="url"
      placeholder="https://sale.591.com.tw/home/house/detail/2/...html" required>
    <button id="listing-import-button" class="secondary-button" type="submit">查核並加入</button>
  </form>
  <p id="listing-import-message" role="status"></p>
`;
document.querySelector(".active-goal").insertAdjacentElement("afterend", importPanelV10);

const resultSearchV10 = document.createElement("label");
resultSearchV10.className = "result-search-control";
resultSearchV10.innerHTML = `
  <span>搜尋全部分類</span>
  <div>
    <input id="current-results-search" type="search"
      placeholder="輸入 591 編號、標題、行政區或來源">
    <button id="clear-results-search" type="button" aria-label="清除搜尋">清除</button>
  </div>
`;
document.querySelector(".result-toolbar").prepend(resultSearchV10);
state.resultQuery = "";

const resultSearchStatusesV10 = [
  "exact_match", "acceptable", "needs_verification", "near_match", "rejected",
];

function allProfileItemsV10() {
  const seen = new Set();
  return resultSearchStatusesV10.flatMap((status) =>
    (state.payload.groups[status] || []).filter((item) => {
      const key = `${item.source || ""}:${item.id}`;
      if (item.profile !== state.activeProfile || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
  );
}

function matchesResultQueryV10(item, query) {
  const variants = (item.variants || []).flatMap((variant) => [
    variant.id, variant.title, variant.source, variant.origin_source,
  ]);
  return [item.id, item.title, item.district, item.source, item.origin_source,
    item.parking, item.broker_name, ...variants]
    .filter(Boolean)
    .join(" ")
    .toLocaleLowerCase("zh-TW")
    .includes(query);
}

const previousRenderResultsV10 = renderResults;
renderResults = function renderResultsV10() {
  const query = String(state.resultQuery || "").trim().toLocaleLowerCase("zh-TW");
  if (!query || !state.payload) {
    previousRenderResultsV10();
    return;
  }
  const items = allProfileItemsV10().filter((item) => matchesResultQueryV10(item, query));
  const filters = document.querySelector("#near-failure-filter-box");
  if (filters) filters.hidden = true;
  document.querySelector("#visible-result-count").textContent =
    `搜尋全部分類：找到 ${items.length} 組`;
  document.querySelector("#results").innerHTML = items.length
    ? items.map(listingCard).join("")
    : emptyState("找不到房源", "可改用 591 編號、標題關鍵字、行政區或來源搜尋。");
};

document.querySelector("#current-results-search").addEventListener("input", (event) => {
  state.resultQuery = event.target.value;
  renderResults();
});
document.querySelector("#clear-results-search").addEventListener("click", () => {
  const input = document.querySelector("#current-results-search");
  input.value = "";
  state.resultQuery = "";
  renderResults();
  input.focus();
});

function classificationMessageV10(listingId, classification) {
  if (!classification) return `已加入房源 ${listingId}，但暫時找不到分類結果。`;
  const parts = [`已加入房源 ${listingId}。分類：${classification.label}`];
  if (classification.score != null) parts[0] += `（符合度 ${classification.score}%）`;
  if (classification.failures && classification.failures.length) {
    parts.push(`不符合：${classification.failures.join("；")}`);
  }
  if (classification.questions && classification.questions.length) {
    parts.push(`待確認：${classification.questions.join("；")}`);
  }
  if (classification.concerns && classification.concerns.length) {
    parts.push(`注意：${classification.concerns.join("；")}`);
  }
  return parts.join(" ");
}

const previousRenderNavigationV10 = renderNavigation;
renderNavigation = function renderNavigationV10() {
  previousRenderNavigationV10();
  document.querySelector("#active-goal-title").textContent =
    state.activeProfile === "大樓公寓華廈" ? "大樓・華廈" :
    document.querySelector(`.goal-card[data-profile="${state.activeProfile}"] strong`).textContent;
  document.querySelector('#search-mode option[value="full"]').textContent =
    "完整盤點（不限刊登時間／滿頁自動拆分）";
  importPanelV10.hidden = state.activeProfile === "預售屋";
};

const previousRenderStatusV10 = renderStatus;
renderStatus = function renderStatusV10(status) {
  previousRenderStatusV10(status);
  document.querySelector("#listing-import-button").disabled = Boolean(status.running);
};

document.querySelector("#listing-import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = document.querySelector("#listing-import-button");
  const message = document.querySelector("#listing-import-message");
  const url = document.querySelector("#listing-import-url").value.trim();
  button.disabled = true;
  message.textContent = "正在開啟房源並核對資料…";
  try {
    const response = await fetch("/api/listings/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: state.activeProfile, url }),
    });
    const payload = await readJsonResponse(response, "房源網址查核失敗");
    state.payload = payload.results;
    state.resultQuery = String(payload.listing_id);
    document.querySelector("#current-results-search").value = state.resultQuery;
    renderNavigation();
    renderResults();
    message.textContent = classificationMessageV10(
      payload.listing_id, payload.classification
    );
  } catch (error) {
    message.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

const previousRenderInsightV10 = renderInsight;
renderInsight = function renderInsightV10() {
  previousRenderInsightV10();
  const diagnostic = state.payload && state.payload.search_diagnostics
    ? state.payload.search_diagnostics[state.activeProfile]
    : null;
  const source = diagnostic && diagnostic.sources
    ? diagnostic.sources["591"]
    : diagnostic;
  if (!source || !source.query_count) return;
  const unresolved = Number(source.unresolved_queries || 0);
  const coverage = document.querySelector("#goal-insight .coverage-summary");
  if (!coverage) return;
  coverage.insertAdjacentHTML("beforeend",
    `<small class="coverage-detail ${unresolved ? "coverage-alert" : ""}">` +
    `591 已執行 ${number(source.query_count)} 組逐區／細分查詢・` +
    `蒐集上限 ${number(source.collection_max_price)} 萬` +
    `${unresolved ? `・仍有 ${number(unresolved)} 組達頁數上限` : "・沒有未解決的滿頁截斷"}` +
    `</small>`
  );
  const detailRequests = Number(source.detail_requests || 0);
  const detailDeferred = Number(source.detail_deferred || 0);
  if (detailRequests || detailDeferred) {
    coverage.insertAdjacentHTML(
      "beforeend",
      `<small class="coverage-detail">詳情已讀 ${number(detailRequests)} 筆` +
      `${detailDeferred ? `・另保留 ${number(detailDeferred)} 筆列表候選待補詳情` : ""}</small>`
    );
  }
};
