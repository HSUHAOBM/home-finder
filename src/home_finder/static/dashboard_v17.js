const PRESALE_STATUS_ORDER_V17 = [
  "exact_match", "acceptable", "needs_verification", "near_match", "rejected",
];

// 行政區中心只用來回答「哪一區有案子」。圖釘會分散排列，絕不代表基地座標。
const DISTRICT_CENTERS_V17 = {
  "新興區": [22.6313, 120.3014], "前金區": [22.6265, 120.2940],
  "苓雅區": [22.6265, 120.3120], "鹽埕區": [22.6242, 120.2842],
  "鼓山區": [22.6500, 120.2745], "旗津區": [22.6123, 120.2684],
  "前鎮區": [22.5905, 120.3147], "三民區": [22.6499, 120.3179],
  "楠梓區": [22.7290, 120.3260], "小港區": [22.5654, 120.3370],
  "左營區": [22.6877, 120.2946], "仁武區": [22.7012, 120.3608],
  "大社區": [22.7310, 120.3477], "岡山區": [22.7971, 120.2950],
  "路竹區": [22.8571, 120.2594], "阿蓮區": [22.8848, 120.3290],
  "田寮區": [22.8660, 120.3930], "燕巢區": [22.7930, 120.3630],
  "橋頭區": [22.7525, 120.3059], "梓官區": [22.7604, 120.2672],
  "彌陀區": [22.7823, 120.2482], "永安區": [22.8182, 120.2247],
  "湖內區": [22.9080, 120.2270], "茄萣區": [22.9066, 120.1823],
  "鳳山區": [22.6251, 120.3571], "大寮區": [22.6072, 120.3950],
  "鳥松區": [22.6625, 120.3727], "林園區": [22.5081, 120.3957],
  "大樹區": [22.6949, 120.4335], "旗山區": [22.8884, 120.4832],
  "美濃區": [22.9000, 120.5420], "六龜區": [22.9955, 120.6330],
  "甲仙區": [23.0817, 120.5914], "杉林區": [22.9960, 120.5380],
  "內門區": [22.9430, 120.4710], "茂林區": [22.8860, 120.6630],
  "桃源區": [23.1600, 120.7600], "那瑪夏區": [23.2750, 120.7200],
};

const PRESALE_STAGE_META_V17 = {
  basic: { label: "只有基本資料", color: "#9a6b3f" },
  partial: { label: "部分資訊公開", color: "#d18a22" },
  complete: { label: "公開資訊較完整", color: "#1d7654" },
};

function allPresalesV17() {
  const seen = new Set();
  const byProject = new Map();
  const groups = state.payload?.groups || {};
  PRESALE_STATUS_ORDER_V17.forEach((status) => {
    (groups[status] || []).forEach((item) => {
      if (item.profile !== "預售屋") return;
      const key = `${item.source || "591"}:${item.id}`;
      if (seen.has(key)) return;
      seen.add(key);
      const projectKey = `${item.district || ""}:${String(item.community || item.title || "").replace(/[^0-9a-z\u4e00-\u9fff]/gi, "").toLowerCase()}`;
      const current = byProject.get(projectKey);
      const sourceLink = { source: item.source || "來源", url: item.url };
      if (!current) {
        byProject.set(projectKey, { ...item, original_status: status, map_sources: [sourceLink] });
        return;
      }
      ["price", "main_area", "total_area", "rooms", "baths", "parking", "address", "community"].forEach((field) => {
        if ((current[field] == null || current[field] === "" || current[field] === 0) && item[field] != null && item[field] !== "" && item[field] !== 0) current[field] = item[field];
      });
      current.questions = [...new Set([...(current.questions || []), ...(item.questions || [])])];
      current.concerns = [...new Set([...(current.concerns || []), ...(item.concerns || [])])];
      current.map_sources.push(sourceLink);
    });
  });
  return [...byProject.values()];
}

function knownPresaleFieldV17(item, field) {
  if (field === "price") return Number(item.price) > 0;
  if (field === "area") return Number(item.main_area) > 0;
  if (field === "rooms") return Number(item.rooms) > 0;
  if (field === "parking") {
    const text = String(item.parking || "").trim();
    return Boolean(text && text !== "待確認" && text !== "未知");
  }
  return false;
}

function presaleStageV17(item) {
  const known = ["price", "area", "rooms", "parking"]
    .filter((field) => knownPresaleFieldV17(item, field)).length;
  if (known === 4) return "complete";
  if (known >= 2) return "partial";
  return "basic";
}

function markerPositionV17(item, indexByDistrict) {
  const center = DISTRICT_CENTERS_V17[item.district];
  if (!center) return null;
  const index = indexByDistrict.get(item.district) || 0;
  indexByDistrict.set(item.district, index + 1);
  if (!index) return center;
  const ring = Math.floor((index - 1) / 8) + 1;
  const angle = ((index - 1) % 8) * Math.PI / 4;
  const radius = 0.0035 * ring;
  return [center[0] + Math.sin(angle) * radius, center[1] + Math.cos(angle) * radius];
}

function presaleMapSearchAddressV17(item) {
  const address = String(item.address || "").trim();
  if (address.startsWith("高雄市")) return address;
  return `高雄市${item.district || ""}${address}`.trim();
}

function presalePopupV17(item, stage) {
  const meta = PRESALE_STAGE_META_V17[stage];
  const price = Number(item.price) > 0 ? `${number(item.price)} 萬` : "總價待現場詢問";
  const area = Number(item.main_area) > 0 ? `主建 ${number(item.main_area)} 坪` : "主建物待確認";
  const rooms = Number(item.rooms) > 0 ? `${number(item.rooms)} 房` : "格局待確認";
  const parking = knownPresaleFieldV17(item, "parking") ? item.parking : "戶別車位待確認";
  const address = presaleMapSearchAddressV17(item);
  const sourceLinks = (item.map_sources || [{ source: item.source || "來源", url: item.url }])
    .filter((link) => link.url)
    .map((link) => `<a href="${safeUrl(link.url)}" target="_blank" rel="noopener">${escapeHtml(link.source)}</a>`).join("");
  return `<article class="presale-map-popup">
    <span style="--stage-color:${meta.color}">${escapeHtml(meta.label)}</span>
    <h3>${escapeHtml(item.title)}</h3>
    <p>${escapeHtml(item.district || "區域待確認")}・${escapeHtml(price)}</p>
    <ul><li>${escapeHtml(area)}</li><li>${escapeHtml(rooms)}</li><li>${escapeHtml(parking)}</li></ul>
    <small>圖釘為行政區約略位置，不是基地座標。</small>
    <div>${sourceLinks}${address ? `<a href="${mapsSearchUrlV14(address)}" target="_blank" rel="noopener">Google Maps 搜尋</a>` : ""}</div>
  </article>`;
}

let presaleMapV17 = null;
let presaleMarkersV17 = [];
let presaleFilterV17 = "all";

function districtSummaryV17(items) {
  const counts = new Map();
  items.forEach((item) => counts.set(item.district || "區域待確認", (counts.get(item.district || "區域待確認") || 0) + 1));
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-TW"));
}

function updatePresaleMarkersV17() {
  const visible = presaleMarkersV17.filter(({ stage }) => presaleFilterV17 === "all" || stage === presaleFilterV17);
  presaleMarkersV17.forEach(({ marker }) => marker.remove());
  visible.forEach(({ marker }) => marker.addTo(presaleMapV17));
  document.querySelector("#presale-map-visible").textContent = `顯示 ${visible.length} 個建案`;
  document.querySelectorAll("[data-presale-stage]").forEach((button) => {
    button.classList.toggle("active", button.dataset.presaleStage === presaleFilterV17);
  });
  const points = visible.map(({ marker }) => marker.getLatLng());
  if (points.length) presaleMapV17.fitBounds(L.latLngBounds(points).pad(0.18), { maxZoom: 12 });
}

function openPresaleMapV17() {
  const items = allPresalesV17();
  const content = document.querySelector("#presale-map-content");
  const summary = districtSummaryV17(items);
  content.innerHTML = `<header class="presale-map-header">
      <div><span class="section-label">PRESALE DISCOVERY MAP</span><h2>預售屋在哪裡</h2><p>先看區域供給，不因總價、坪數或車位尚未公開而隱藏建案。</p></div>
      <button class="presale-map-close" type="button" aria-label="關閉">×</button>
    </header>
    <div class="presale-map-filters" role="group" aria-label="公開資料完整度">
      <button type="button" data-presale-stage="all">全部 ${items.length}</button>
      ${Object.entries(PRESALE_STAGE_META_V17).map(([key, meta]) => `<button type="button" data-presale-stage="${key}"><i style="--stage-color:${meta.color}"></i>${meta.label} ${items.filter((item) => presaleStageV17(item) === key).length}</button>`).join("")}
      <span id="presale-map-visible"></span>
    </div>
    <div class="presale-map-layout">
      <aside><strong>行政區建案數</strong>${summary.map(([district, count]) => `<button type="button" data-presale-district="${escapeHtml(district)}"><span>${escapeHtml(district)}</span><b>${count}</b></button>`).join("") || "<p>尚未搜尋到預售建案。</p>"}</aside>
      <div><div id="presale-map-canvas"></div><p class="presale-map-notice">圖釘依行政區中心分散排列，只用來快速看哪一區有案子；基地位置請點選建案後以地址、建照或現場資料確認。地圖底圖由 OpenStreetMap 提供。</p></div>
    </div>`;
  document.querySelector("#presale-map-dialog").showModal();
  content.querySelector(".presale-map-close").addEventListener("click", () => document.querySelector("#presale-map-dialog").close());
  if (!items.length || typeof L === "undefined") {
    if (typeof L === "undefined") document.querySelector("#presale-map-canvas").innerHTML = "<p>地圖元件無法載入；左側仍可查看各行政區建案數。</p>";
    return;
  }
  presaleMapV17?.remove();
  presaleMapV17 = L.map("presale-map-canvas", { zoomControl: true }).setView([22.72, 120.34], 10);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18, attribution: "&copy; OpenStreetMap contributors",
  }).addTo(presaleMapV17);
  const indexByDistrict = new Map();
  presaleMarkersV17 = items.map((item) => {
    const stage = presaleStageV17(item);
    const position = markerPositionV17(item, indexByDistrict);
    if (!position) return null;
    const marker = L.circleMarker(position, {
      radius: 9, weight: 2, color: "#fff", fillColor: PRESALE_STAGE_META_V17[stage].color, fillOpacity: 0.94,
    }).bindPopup(presalePopupV17(item, stage), { maxWidth: 310 });
    marker.presaleDistrict = item.district;
    return { marker, stage, item };
  }).filter(Boolean);
  presaleFilterV17 = "all";
  updatePresaleMarkersV17();
  setTimeout(() => presaleMapV17.invalidateSize(), 0);
}

const presaleMapButtonV17 = document.createElement("button");
presaleMapButtonV17.id = "presale-map-button";
presaleMapButtonV17.className = "tab presale-map-button";
presaleMapButtonV17.type = "button";
presaleMapButtonV17.textContent = "地圖探索";
document.querySelector(".tabs").appendChild(presaleMapButtonV17);

const presaleMapDialogV17 = document.createElement("dialog");
presaleMapDialogV17.id = "presale-map-dialog";
presaleMapDialogV17.innerHTML = '<div id="presale-map-content"></div>';
document.body.appendChild(presaleMapDialogV17);

presaleMapButtonV17.addEventListener("click", openPresaleMapV17);
presaleMapDialogV17.addEventListener("click", (event) => { if (event.target === presaleMapDialogV17) presaleMapDialogV17.close(); });
document.querySelector("#presale-map-content").addEventListener("click", (event) => {
  const filter = event.target.closest("[data-presale-stage]");
  if (filter && presaleMapV17) {
    presaleFilterV17 = filter.dataset.presaleStage;
    updatePresaleMarkersV17();
    return;
  }
  const district = event.target.closest("[data-presale-district]");
  if (!district || !presaleMapV17) return;
  const match = presaleMarkersV17.find(({ item }) => item.district === district.dataset.presaleDistrict);
  if (match) {
    presaleMapV17.setView(match.marker.getLatLng(), 12);
    match.marker.openPopup();
  }
});

function syncPresaleMapButtonV17() {
  presaleMapButtonV17.hidden = state.activeProfile !== "預售屋";
  if (!presaleMapButtonV17.hidden) presaleMapButtonV17.textContent = `地圖探索 ${allPresalesV17().length}`;
}

const previousRenderNavigationV17 = renderNavigation;
renderNavigation = function renderNavigationV17() {
  previousRenderNavigationV17();
  syncPresaleMapButtonV17();
};
document.querySelectorAll(".goal-card").forEach((card) => card.addEventListener("click", syncPresaleMapButtonV17));
syncPresaleMapButtonV17();

window.presaleStageV17 = presaleStageV17;
