const searchGrid = document.querySelector(".settings-block .form-grid.compact");
if (searchGrid) {
  searchGrid.insertAdjacentHTML("beforeend", `
    <label>每種中古屋至少讀幾頁
      <input id="search-pages" type="number" min="3" max="10" required>
    </label>
    <label>中古屋刊登時間
      <select id="publish-days" required>
        <option value="1">一天內</option><option value="3">三天內（預設）</option>
        <option value="5">五天內</option><option value="7">七天內</option>
        <option value="15">十五天內</option><option value="30">三十天內</option>
        <option value="0">不限</option>
      </select>
    </label>`);
  document.querySelector("#resale-details").parentElement.firstChild.textContent = "每種中古屋詳情上限";
  document.querySelector("#presale-details").max = "30";
  searchGrid.insertAdjacentHTML("afterend", '<p class="source-note">中古屋會分開爬大樓與透天，各自至少 3 頁；預售屋沒有有效第二頁，改為讀完勾選行政區的列表，並以爬蟲首次發現時間判斷新案。</p>');
}

const condoSwitches = document.querySelector(".condo-settings .switches");
if (condoSwitches) {
  condoSwitches.insertAdjacentHTML("beforeend", `
    <label><input id="condo-require-high-floor" type="checkbox">樓層至少達全棟指定比例</label>
    <label class="floor-ratio-label">最低樓層比例
      <select id="condo-min-floor-ratio">
        <option value="0.5">1/2</option><option value="0.6">3/5</option>
        <option value="0.6666666666666666">2/3（預設）</option>
        <option value="0.75">3/4</option><option value="0.8">4/5</option>
      </select>
    </label>`);
}

const previousFillSettingsForm = fillSettingsForm;
fillSettingsForm = function fillSettingsFormV4() {
  previousFillSettingsForm();
  const search = state.settings.search;
  document.querySelector("#search-pages").value = search.pages;
  document.querySelector("#publish-days").value = search.publish_days;
  const condo = state.settings.profiles["大樓公寓華廈"];
  document.querySelector("#condo-require-high-floor").checked = condo.require_high_floor;
  document.querySelector("#condo-min-floor-ratio").value = String(condo.min_floor_ratio);
};

const previousCollectSettings = collectSettings;
collectSettings = function collectSettingsV4() {
  const settings = previousCollectSettings();
  settings.search.pages = Number(document.querySelector("#search-pages").value);
  settings.search.publish_days = Number(document.querySelector("#publish-days").value);
  settings.profiles["大樓公寓華廈"].require_high_floor = document.querySelector("#condo-require-high-floor").checked;
  settings.profiles["大樓公寓華廈"].min_floor_ratio = Number(document.querySelector("#condo-min-floor-ratio").value);
  return settings;
};

const previousGoalRule = goalRule;
goalRule = function goalRuleV4(profile) {
  let text = previousGoalRule(profile);
  if (!state.settings) return text;
  const search = state.settings.search;
  if (profile === "大樓公寓華廈" && state.settings.profiles[profile].require_high_floor) text += "・樓層 ≥ 2/3";
  if (profile !== "預售屋") text += `・近 ${search.publish_days || "不限"} 天・${search.pages} 頁`;
  return text;
};

const previousGoalDescription = goalDescription;
goalDescription = function goalDescriptionV4(profile) {
  let text = previousGoalDescription(profile);
  if (!state.settings) return text;
  if (profile === "大樓公寓華廈" && state.settings.profiles[profile].require_high_floor) {
    text += " 樓層必須至少達全棟 2/3；例如 15 樓大樓須在 10 樓以上，樓層不明列待確認。";
  }
  return text;
};

function lifecycleLabel(item) {
  const labels = { new: "本次新發現", updated: "資料有更新", seen: "曾看過・本次仍在", possibly_removed: "詳情可能已下架" };
  return labels[item.lifecycle_status] || "尚未建立追蹤";
}

function dateText(value) {
  if (!value) return "—";
  try { return new Date(value).toLocaleString("zh-TW"); } catch { return value; }
}

const previousListingCard = listingCard;
listingCard = function listingCardV4(item) {
  const html = previousListingCard(item);
  const tracking = `<div class="tracking-row">
    <span class="lifecycle ${escapeHtml(item.lifecycle_status || "unknown")}">${escapeHtml(lifecycleLabel(item))}</span>
    <span>${escapeHtml(item.listing_updated_text || "591 未提供更新文字")}</span>
    <span>首次發現：${escapeHtml(dateText(item.first_seen_at))}</span>
  </div>`;
  return html.replace("<h2>", `${tracking}<h2>`);
};

const previousRenderNavigation = renderNavigation;
renderNavigation = function renderNavigationV4() {
  previousRenderNavigation();
  if (!state.settings) return;
  const search = state.settings.search;
  document.querySelector("#criteria-summary").insertAdjacentHTML(
    "beforeend",
    `<span>中古屋近 ${search.publish_days || "不限"} 天</span><span>每種 ${search.pages} 頁</span>`
  );
};
