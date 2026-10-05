state.compareFavorites = new Set();
state.commuteDestinations = [];
state.mapWorkspaceItems = [];
let overviewMapV14 = null;
let overviewMarkersV14 = [];

const MAP_STATUS_META_V14 = {
  exact_match: { label: "完全符合", color: "#1d7654" },
  acceptable: { label: "可接受", color: "#8a741d" },
  needs_verification: { label: "待確認", color: "#5b7187" },
  near_match: { label: "差強人意", color: "#b77719" },
  rejected: { label: "已排除", color: "#a34f42" },
};

const MAP_DISTRICT_CENTERS_V14 = {
  "三民區": [22.6499, 120.3179], "左營區": [22.6877, 120.2946],
  "楠梓區": [22.7290, 120.3260], "橋頭區": [22.7525, 120.3059],
  "岡山區": [22.7971, 120.2950], "燕巢區": [22.7930, 120.3630],
  "仁武區": [22.7012, 120.3608], "大社區": [22.7310, 120.3477],
};

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
  if (item.community) {
    html = html.replace(
      /(<span class="badge [^"]+">[^<]*<\/span>)/,
      `$1<span class="listing-community" title="${escapeHtml(item.community)}"><small>社區</small><b>${escapeHtml(item.community)}</b></span>`
    );
  }
  if (item.is_favorite) html = html.replace("<h2>", `${compareToggleV14(item)}<h2>`);
  return html;
};

function activeMapItemsV14() {
  if (state.activeStatus === "favorites") return state.payload?.favorites || [];
  return profileItems(state.activeProfile, "exact_match")
    .map((item) => ({ ...item, map_status: "exact_match" }))
    .filter((item) => item.lifecycle_status !== "possibly_removed" && item.url_availability_status !== "removed");
}

function activeMapTitleV14() {
  if (state.activeStatus === "favorites") return "收藏地圖與通勤";
  return `${PROFILE_META[state.activeProfile]?.title || state.activeProfile}・完全符合地圖`;
}

function syncCompareBarV14() {
  const active = state.activeStatus === "favorites";
  const bar = document.querySelector("#favorite-compare-bar");
  bar.hidden = !active;
  const mapButton = document.querySelector("#favorite-map-button");
  mapButton.hidden = false;
  mapButton.textContent = active ? "收藏地圖" : "房源地圖";
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

function overviewMarkerPositionV14(item, indexByDistrict) {
  const center = MAP_DISTRICT_CENTERS_V14[item.district];
  if (!center) return null;
  const index = indexByDistrict.get(item.district) || 0;
  indexByDistrict.set(item.district, index + 1);
  if (!index) return center;
  const ring = Math.floor((index - 1) / 12) + 1;
  const angle = ((index - 1) % 12) * Math.PI / 6;
  const radius = .0028 * ring;
  return [center[0] + Math.sin(angle) * radius, center[1] + Math.cos(angle) * radius];
}

function overviewPopupV14(item) {
  const meta = MAP_STATUS_META_V14[item.map_status] || { label: "收藏", color: "#1d7654" };
  const price = item.price != null ? `${number(item.price)} 萬` : "價格待確認";
  const layout = `${item.rooms ?? "?"} 房・${item.baths ?? "?"} 衛`;
  const address = fullAddressV14(item);
  return `<article class="overview-map-popup">
    <span style="--marker-color:${meta.color}">${escapeHtml(meta.label)}</span>
    <h3>${escapeHtml(item.title)}</h3>
    <p><b>${escapeHtml(price)}</b>・${escapeHtml(item.district || "區域待確認")}</p>
    <ul><li>${escapeHtml(layout)}</li><li>${escapeHtml(item.parking || "車位待確認")}</li>${item.community ? `<li>${escapeHtml(item.community)}</li>` : ""}</ul>
    <small>圖釘為行政區內約略位置，不代表實際棟別。</small>
    <div><a href="${safeUrl(item.url)}" target="_blank" rel="noopener">開啟原始房源</a>${address ? `<a href="${mapsSearchUrlV14(address)}" target="_blank" rel="noopener">Google Maps 搜尋</a>` : ""}</div>
  </article>`;
}

function mapWorkspaceV14(items, title = "房源地圖") {
  const counts = Object.entries(MAP_STATUS_META_V14).map(([status, meta]) =>
    `<span><i style="--marker-color:${meta.color}"></i>${meta.label} ${items.filter((item) => item.map_status === status).length}</span>`
  ).join("");
  return `<header class="overview-map-header"><div><span class="section-label">PROPERTY MAP</span><h2>${escapeHtml(title)}</h2><p>地圖一次顯示目前分類的完全符合房源；關閉後可回原本列表逐筆查看。</p></div></header>
    <div class="overview-map-legend">${counts}<b>共 ${items.length} 筆</b></div>
    <div class="favorite-map-layout"><div class="favorite-map-list">${items.map((item, index) => {
      const meta = MAP_STATUS_META_V14[item.map_status] || { label: "收藏", color: "#1d7654" };
      return `<button type="button" data-map-index="${index}"><i style="--marker-color:${meta.color}"></i><strong>${escapeHtml(item.title)}</strong>${item.community ? `<em>${escapeHtml(item.community)}</em>` : ""}<span>${escapeHtml(item.district || "區域待確認")}・${item.price != null ? `${number(item.price)} 萬` : "價格待確認"}</span></button>`;
    }).join("") || "<p>目前沒有可顯示的刊登中房源。</p>"}</div><div class="favorite-map-detail"><div id="overview-map-canvas"></div><p class="map-accuracy-note">多數房仲只公開路名或社區，圖釘依行政區中心分散排列，僅供區域總覽；實際位置請以原始房源及現場確認為準。</p></div></div>`;
}

function initializeOverviewMapV14(items) {
  if (!items.length || typeof L === "undefined") {
    if (typeof L === "undefined") document.querySelector("#overview-map-canvas").innerHTML = "<p>地圖元件無法載入，仍可使用左側房源清單。</p>";
    return;
  }
  overviewMapV14?.remove();
  overviewMapV14 = L.map("overview-map-canvas", { zoomControl: true }).setView([22.72, 120.34], 10);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18, attribution: "&copy; OpenStreetMap contributors",
  }).addTo(overviewMapV14);
  const indexByDistrict = new Map();
  overviewMarkersV14 = items.map((item, index) => {
    const position = overviewMarkerPositionV14(item, indexByDistrict);
    if (!position) return null;
    const meta = MAP_STATUS_META_V14[item.map_status] || { color: "#1d7654" };
    const marker = L.circleMarker(position, {
      radius: 7, weight: 2, color: "#fff", fillColor: meta.color, fillOpacity: .9,
    }).bindPopup(overviewPopupV14(item), { maxWidth: 320 });
    marker.addTo(overviewMapV14);
    return { marker, item, index };
  }).filter(Boolean);
  const points = overviewMarkersV14.map(({ marker }) => marker.getLatLng());
  if (points.length) overviewMapV14.fitBounds(L.latLngBounds(points).pad(.14), { maxZoom: 12 });
  setTimeout(() => overviewMapV14.invalidateSize(), 0);
}

document.querySelector("#favorite-map-button").addEventListener("click", () => {
  if (state.activeStatus !== "favorites") {
    const params = new URLSearchParams({profile:state.activeProfile,status:state.activeStatus});
    const sortAliases = {newest:'newest-desc',price:'price-asc',failures:'failures-asc'};
    const selectedSort = document.querySelector('#result-sort')?.value || 'metric-desc';
    params.set('sort', sortAliases[selectedSort] || selectedSort);
    params.set('district', document.querySelector('#result-district')?.value || '');
    params.set('baths', document.querySelector('#result-baths')?.value || '');
    params.set('failure', state.nearFailureFilter || '');
    window.open(`/property-map?${params}`, "_blank", "noopener");
    return;
  }
  state.mapWorkspaceItems = activeMapItemsV14();
  document.querySelector("#favorite-workspace-content").innerHTML = mapWorkspaceV14(
    state.mapWorkspaceItems, activeMapTitleV14()
  );
  workspaceV14.showModal();
  initializeOverviewMapV14(state.mapWorkspaceItems);
});
document.querySelector("#favorite-workspace-content").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-map-index]");
  if (!button) return;
  const index = Number(button.dataset.mapIndex);
  const match = overviewMarkersV14.find((entry) => entry.index === index);
  if (!match || !overviewMapV14) return;
  document.querySelectorAll("button[data-map-index]").forEach((item) => item.classList.toggle("active", item === button));
  overviewMapV14.setView(match.marker.getLatLng(), Math.max(overviewMapV14.getZoom(), 12));
  match.marker.openPopup();
});
workspaceV14.querySelector(".workspace-close").addEventListener("click", () => workspaceV14.close());
workspaceV14.addEventListener("click", (event) => { if (event.target === workspaceV14) workspaceV14.close(); });

fetch("/api/commute-settings").then((response) => readJsonResponse(response, "讀取通勤地點失敗")).then((payload) => { state.commuteDestinations = payload.destinations || []; }).catch((error) => { document.querySelector("#status-message").textContent = error.message; });
