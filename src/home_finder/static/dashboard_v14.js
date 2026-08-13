state.compareFavorites = new Set();
state.commuteDestinations = [];

function fullAddressV14(item) {
  const address = String(item.address || "").trim();
  const community = String(item.community || "").trim();
  const base = `高雄市${item.district || ""}`;
  if (!address) return community ? `${base} ${community}` : "";
  const locatedAddress = address.startsWith("高雄市")
    ? address : `${base}${address}`;
  if (/\d+(?:之\d+)?號/.test(locatedAddress)) return locatedAddress;
  return community ? `${base} ${community}` : locatedAddress;
}

function mapsSearchUrlV14(address, embed = false) {
  const query = encodeURIComponent(address);
  return embed
    ? `https://maps.google.com/maps?q=${query}&output=embed`
    : `https://www.google.com/maps/search/?api=1&query=${query}`;
}

function directionsUrlV14(origin, destination, mode) {
  const travelmode = mode === "transit" ? "transit" : "driving";
  return `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}&travelmode=${travelmode}`;
}

const favoriteTabV14 = document.querySelector('[data-status="favorites"]');
favoriteTabV14.insertAdjacentHTML("afterend", '<button id="favorite-map-button" class="tab favorite-tools-tab" type="button">地圖模式</button>');
document.querySelector("#favorite-status-filters").insertAdjacentHTML("afterend", `
  <section id="favorite-compare-bar" class="favorite-compare-bar" hidden>
    <span>已選 <b id="favorite-compare-count">0</b>/4 間</span>
    <button id="favorite-compare-open" type="button" disabled>開始比較</button>
    <button id="favorite-compare-clear" type="button">清除</button>
  </section>`);

const workspaceV14 = document.createElement("dialog");
workspaceV14.id = "favorite-workspace";
workspaceV14.className = "favorite-workspace";
workspaceV14.innerHTML = '<div class="favorite-workspace-body"><button class="workspace-close" type="button" aria-label="關閉">×</button><div id="favorite-workspace-content"></div></div>';
document.body.appendChild(workspaceV14);

function compareToggleV14(item) {
  if (!item.is_favorite) return "";
  const key = `${item.source || "591"}:${item.id}`;
  const selected = state.compareFavorites.has(key);
  return `<label class="favorite-compare-toggle"><input type="checkbox" data-compare-key="${escapeHtml(key)}" ${selected ? "checked" : ""}> 加入比較</label>`;
}

const previousListingCardV14 = listingCard;
listingCard = function listingCardV14(item) {
  let html = previousListingCardV14(item);
  if (item.is_favorite) html = html.replace("<h2>", `${compareToggleV14(item)}<h2>`);
  return html;
};

function syncCompareBarV14() {
  const active = state.activeStatus === "favorites";
  const bar = document.querySelector("#favorite-compare-bar");
  bar.hidden = !active;
  document.querySelector("#favorite-map-button").hidden = !active;
  document.querySelector("#favorite-compare-count").textContent = state.compareFavorites.size;
  document.querySelector("#favorite-compare-open").disabled = state.compareFavorites.size < 2;
}

const previousRenderNavigationV14 = renderNavigation;
renderNavigation = function renderNavigationV14() {
  previousRenderNavigationV14();
  syncCompareBarV14();
};

document.querySelector("#results").addEventListener("change", (event) => {
  const input = event.target.closest("input[data-compare-key]");
  if (!input) return;
  if (input.checked && state.compareFavorites.size >= 4) {
    input.checked = false;
    document.querySelector("#status-message").textContent = "一次最多比較 4 間收藏";
    return;
  }
  if (input.checked) state.compareFavorites.add(input.dataset.compareKey);
  else state.compareFavorites.delete(input.dataset.compareKey);
  syncCompareBarV14();
});

function selectedFavoritesV14() {
  return (state.payload?.favorites || []).filter((item) => state.compareFavorites.has(`${item.source || "591"}:${item.id}`));
}

function compareTableV14(items) {
  const rows = [
    ["總價", (i) => i.price != null ? `${i.price} 萬` : "待確認"],
    ["權狀單價", (i) => i.price_per_total_area != null ? `${i.price_per_total_area} 萬/坪` : "待確認"],
    ["室內單價", (i) => i.price_per_main_area != null ? `${i.price_per_main_area} 萬/坪` : "待確認"],
    ["屋齡", (i) => i.age != null ? `${i.age} 年` : "待確認"],
    ["格局", (i) => `${i.rooms ?? "?"} 房・${i.baths ?? "?"} 衛`],
    ["樓層", (i) => `${i.floor ?? "?"}/${i.total_floors ?? "?"} 樓`],
    ["車位", (i) => i.parking || "待確認"],
    ["地址", (i) => fullAddressV14(i) || "待確認"],
    ["不符合", (i) => (i.failures || []).join("；") || "無"],
    ["我的備註", (i) => i.favorite_note || "尚未填寫"],
  ];
  return `<h2>收藏比較</h2><p>並排查看 2～4 間收藏；房貸可回卡片個別試算。</p><div class="compare-scroll"><table class="favorite-compare-table"><thead><tr><th>項目</th>${items.map((i) => `<th><a href="${safeUrl(i.url)}" target="_blank" rel="noopener">${escapeHtml(i.title)}</a><small>${escapeHtml(i.district || "")}</small></th>`).join("")}</tr></thead><tbody>${rows.map(([label, value]) => `<tr><th>${label}</th>${items.map((i) => `<td>${escapeHtml(value(i))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

document.querySelector("#favorite-compare-open").addEventListener("click", () => {
  document.querySelector("#favorite-workspace-content").innerHTML = compareTableV14(selectedFavoritesV14());
  workspaceV14.showModal();
});
document.querySelector("#favorite-compare-clear").addEventListener("click", () => { state.compareFavorites.clear(); renderResults(); syncCompareBarV14(); });

function commuteLinksV14(item) {
  const origin = fullAddressV14(item);
  if (!origin) return '<span class="map-address-warning">地址待確認，無法建立路線</span>';
  return state.commuteDestinations.map((destination) => `<div class="commute-destination"><strong>${escapeHtml(destination.name)}</strong><span>${escapeHtml(destination.address)}</span><div><a href="${directionsUrlV14(origin, destination.address, "driving")}" target="_blank" rel="noopener">開車／機車路線</a><a href="${directionsUrlV14(origin, destination.address, "transit")}" target="_blank" rel="noopener">大眾運輸</a></div></div>`).join("");
}

function mapWorkspaceV14(items) {
  const located = items.filter((item) => fullAddressV14(item));
  const first = located[0];
  return `<h2>收藏地圖與通勤</h2><p class="map-accuracy-note">房仲多只提供路名或巷名，地圖為約略位置，不代表實際棟別。</p><div class="favorite-map-layout"><div class="favorite-map-list">${items.map((item, index) => `<button type="button" data-map-index="${index}" ${fullAddressV14(item) ? "" : "disabled"}><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(fullAddressV14(item) || "地址待確認")}</span></button>`).join("")}</div><div class="favorite-map-detail">${first ? `<iframe title="房源約略位置" src="${mapsSearchUrlV14(fullAddressV14(first), true)}" loading="lazy"></iframe><h3>${escapeHtml(first.title)}</h3><a href="${mapsSearchUrlV14(fullAddressV14(first))}" target="_blank" rel="noopener">在 Google Maps 開啟</a><div id="commute-links">${commuteLinksV14(first)}</div>` : "<p>收藏目前沒有可用地址。</p>"}</div></div>`;
}

document.querySelector("#favorite-map-button").addEventListener("click", () => {
  document.querySelector("#favorite-workspace-content").innerHTML = mapWorkspaceV14(state.payload?.favorites || []);
  workspaceV14.showModal();
});
document.querySelector("#favorite-workspace-content").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-map-index]");
  if (!button) return;
  const item = (state.payload?.favorites || [])[Number(button.dataset.mapIndex)];
  const detail = document.querySelector(".favorite-map-detail");
  detail.innerHTML = `<iframe title="房源約略位置" src="${mapsSearchUrlV14(fullAddressV14(item), true)}" loading="lazy"></iframe><h3>${escapeHtml(item.title)}</h3><a href="${mapsSearchUrlV14(fullAddressV14(item))}" target="_blank" rel="noopener">在 Google Maps 開啟</a><div id="commute-links">${commuteLinksV14(item)}</div>`;
});
workspaceV14.querySelector(".workspace-close").addEventListener("click", () => workspaceV14.close());
workspaceV14.addEventListener("click", (event) => { if (event.target === workspaceV14) workspaceV14.close(); });

fetch("/api/commute-settings").then((response) => readJsonResponse(response, "讀取通勤地點失敗")).then((payload) => { state.commuteDestinations = payload.destinations || []; }).catch((error) => { document.querySelector("#status-message").textContent = error.message; });
