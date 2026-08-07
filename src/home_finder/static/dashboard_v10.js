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
    renderNavigation();
    renderResults();
    message.textContent = `已加入房源 ${payload.listing_id}，並依目前條件完成分類。`;
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
};
