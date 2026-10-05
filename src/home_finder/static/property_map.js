const PROFILE_LABELS = { "大樓公寓華廈":"大樓・華廈", "透天別墅":"透天・車墅", "預售屋":"預售屋" };
const STATUS_META = {
  exact_match:{ label:"完全符合", color:"#1d7654" },
  acceptable:{ label:"可接受", color:"#8a741d" },
  needs_verification:{ label:"待確認", color:"#4d718c" },
  near_match:{ label:"差強人意", color:"#b77719" },
  rejected:{ label:"已排除", color:"#a34f42" },
  favorites:{ label:"已收藏", color:"#8f4f78" },
};
// 與首頁預售地圖相同的行政區約略中心；不是房源門牌位置。
const DISTRICT_CENTERS = {
  "新興區":[22.6313,120.3014], "前金區":[22.6265,120.2940], "苓雅區":[22.6265,120.3120], "鹽埕區":[22.6242,120.2842],
  "鼓山區":[22.6500,120.2745], "旗津區":[22.6123,120.2684], "前鎮區":[22.5905,120.3147], "三民區":[22.6499,120.3179],
  "楠梓區":[22.7290,120.3260], "小港區":[22.5654,120.3370], "左營區":[22.6877,120.2946], "仁武區":[22.7012,120.3608],
  "大社區":[22.7310,120.3477], "岡山區":[22.7971,120.2950], "路竹區":[22.8571,120.2594], "阿蓮區":[22.8848,120.3290],
  "田寮區":[22.8660,120.3930], "燕巢區":[22.7930,120.3630], "橋頭區":[22.7525,120.3059], "梓官區":[22.7604,120.2672],
  "彌陀區":[22.7823,120.2482], "永安區":[22.8182,120.2247], "湖內區":[22.9080,120.2270], "茄萣區":[22.9066,120.1823],
  "鳳山區":[22.6251,120.3571], "大寮區":[22.6072,120.3950], "鳥松區":[22.6625,120.3727], "林園區":[22.5081,120.3957],
  "大樹區":[22.6949,120.4335], "旗山區":[22.8884,120.4832], "美濃區":[22.9000,120.5420], "六龜區":[22.9955,120.6330],
  "甲仙區":[23.0817,120.5914], "杉林區":[22.9960,120.5380], "內門區":[22.9430,120.4710], "茂林區":[22.8860,120.6630],
  "桃源區":[23.1600,120.7600], "那瑪夏區":[23.2750,120.7200]
};
const initialFilters = new URLSearchParams(window.location.search);
const state = { payload:null, items:[], visible:[], markers:[], selected:null, map:null, status:"exact_match" };
let profile = PROFILE_LABELS[window.INITIAL_MAP_PROFILE] ? window.INITIAL_MAP_PROFILE : "大樓公寓華廈";
const requestedStatus = STATUS_META[window.INITIAL_MAP_STATUS] ? window.INITIAL_MAP_STATUS : "exact_match";
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
const numberText = (value) => value == null || value === "" ? "待確認" : new Intl.NumberFormat("zh-TW", { maximumFractionDigits:2 }).format(value);
const safeUrl = (value) => /^https:\/\//.test(String(value || "")) ? String(value) : "#";

function itemKey(item) { return `${item.source || "來源"}:${item.id}`; }
function itemScore(item) {
  const value = item.metric_value;
  return value == null || value === "" || !Number.isFinite(Number(value)) ? null : Number(value);
}
function failureCategory(reason) {
  const text = String(reason || "");
  if (/總價|價格/.test(text)) return "總價";
  if (/無汽車位|完全沒車位|無車位|車位[^，；：]*為無/.test(text)) return "無車位";
  if (/不是平面車位|非平面車位|機械車位|機械式|機械上層|機械下層/.test(text)) return "非平面車位";
  if (/車位|汽車位/.test(text)) return "車位";
  if (/主建物|銷售坪數|坪數|坪門檻/.test(text)) return "坪數";
  if (/樓層|位於.*樓|全棟/.test(text)) return "樓層";
  if (/房數|房間|\d+房/.test(text)) return "房數";
  if (/衛浴|浴室|\d+衛/.test(text)) return "衛浴";
  if (/屋齡|屋況|年/.test(text)) return "屋齡";
  if (/型態|預售屋|中古屋|透天|公寓|華廈|大樓/.test(text)) return "物件類型";
  if (/花園|庭院/.test(text)) return "庭院";
  return "其他";
}
function failureCategories(item) { return [...new Set((item.failures || []).map(failureCategory))]; }
function numericSort(items, field, descending = false) {
  return items.sort((a, b) => {
    const first = Number(a[field]); const second = Number(b[field]);
    const firstMissing = !Number.isFinite(first) || first <= 0;
    const secondMissing = !Number.isFinite(second) || second <= 0;
    if (firstMissing !== secondMissing) return firstMissing ? 1 : -1;
    if (firstMissing) return (a.price || 999999) - (b.price || 999999);
    return descending ? second - first : first - second;
  });
}
function sortedItems(items) {
  const copy = [...items];
  switch (document.querySelector("#map-sort").value) {
    case "failures-asc": return copy.sort((a,b) => (a.condition_gap_score || 0) - (b.condition_gap_score || 0) || (a.failures || []).length - (b.failures || []).length || failureCategories(a).join('、').localeCompare(failureCategories(b).join('、'), 'zh-TW'));
    case "failures-desc": return copy.sort((a,b) => (b.condition_gap_score || 0) - (a.condition_gap_score || 0) || (b.failures || []).length - (a.failures || []).length);
    case "price-asc": return numericSort(copy, "price");
    case "price-desc": return numericSort(copy, "price", true);
    case "total-unit-asc": return numericSort(copy, "price_per_total_area");
    case "main-unit-asc": return numericSort(copy, "price_per_main_area");
    case "age-asc": return numericSort(copy, "age");
    case "age-desc": return numericSort(copy, "age", true);
    case "baths-asc": return numericSort(copy, "baths");
    case "baths-desc": return numericSort(copy, "baths", true);
    case "total-unit-desc": return numericSort(copy, "price_per_total_area", true);
    case "main-unit-desc": return numericSort(copy, "price_per_main_area", true);
    case "metric-asc": return copy.sort((a,b) => (itemScore(a) || 0) - (itemScore(b) || 0) || (a.price || 999999) - (b.price || 999999));
    case "floor": return copy.sort((a,b) => (b.floor || 0)/(b.total_floors || 999) - (a.floor || 0)/(a.total_floors || 999));
    case "newest-asc": return copy.sort((a,b) => String(a.first_seen_at || '').localeCompare(String(b.first_seen_at || '')));
    case "newest-desc": return copy.sort((a,b) => String(b.first_seen_at || "").localeCompare(String(a.first_seen_at || "")));
    default: return copy.sort((a,b) => (itemScore(b) || 0) - (itemScore(a) || 0) || (a.price || 999999) - (b.price || 999999));
  }
}
function stablePosition(item, order) {
  const center = DISTRICT_CENTERS[item.district];
  if (!center) return null;
  let hash = 0;
  for (const char of itemKey(item)) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  const ring = 1 + ((hash >>> 9) % 5);
  const angle = ((hash % 360) / 180) * Math.PI;
  const radius = .0024 * ring;
  return [center[0] + Math.sin(angle) * radius, center[1] + Math.cos(angle) * radius];
}
function facts(item) {
  return [
    ["權狀坪數", item.total_area == null ? "待確認" : `${numberText(item.total_area)} 坪`],
    ["主建物", item.main_area == null ? "待確認" : `${numberText(item.main_area)} 坪`],
    ["權狀單價", item.price_per_total_area == null ? "待確認" : `${numberText(item.price_per_total_area)} 萬/坪`],
    ["主建單價", item.price_per_main_area == null ? "待確認" : `${numberText(item.price_per_main_area)} 萬/坪`],
    ["格局", `${numberText(item.rooms)} 房・${numberText(item.baths)} 衛`],
    ["樓層", item.floor == null ? "待確認" : `${item.floor}/${item.total_floors ?? "?"} 樓`],
    ["屋齡", item.age == null ? "待確認" : `${numberText(item.age)} 年`],
    ["車位", item.parking || "待確認"],
  ];
}
function renderDetail(item) {
  state.selected = itemKey(item);
  document.querySelectorAll("[data-item-key]").forEach((button) => button.classList.toggle("active", button.dataset.itemKey === state.selected));
  const hiddenMapNotes = new Set(["本次搜尋未再次找到；網址尚未確認是否下架"]);
  const visibleConcerns = (item.concerns || []).filter((row) => !hiddenMapNotes.has(String(row).trim()));
  const blocks = [["符合優點", item.strengths], ["待確認", item.questions], ["注意事項", visibleConcerns], ["不符合條件", item.failures]]
    .filter(([, rows]) => rows?.length)
    .map(([title, rows]) => `<section class="detail-block"><strong>${title}</strong><ul>${rows.map((row) => `<li>${esc(row)}</li>`).join("")}</ul></section>`).join("");
  const meta = STATUS_META[state.status];
  document.querySelector("#map-detail").innerHTML = `<span class="status" style="color:${meta.color}">${meta.label}・${esc(item.source || "來源")}</span><h2>${esc(item.title)}</h2><p class="community">${esc(item.district || "區域待確認")}${item.community ? `・${esc(item.community)}` : ""}</p><p class="price" style="color:${meta.color}">${numberText(item.price)} 萬</p><div class="fact-grid">${facts(item).map(([label,value]) => `<div class="fact"><span>${label}</span><b>${esc(value)}</b></div>`).join("")}</div>${blocks}<a class="source-link" href="${safeUrl(item.url)}" target="_blank" rel="noopener">開啟原始房源</a>`;
}
function renderList() {
  document.querySelector("#map-list").innerHTML = state.visible.map((item) => {
    const failureCount = (item.failures || []).length;
    const score = itemScore(item);
    const metric = score == null ? "" : `${item.metric_label || '理想條件符合度'} ${numberText(score)}%`;
    const summary = [failureCount ? `不符 ${failureCount} 項` : "", metric].filter(Boolean).join("・");
    const unitPrice = item.price_per_total_area == null ? "" : `・權狀 ${numberText(item.price_per_total_area)} 萬/坪`;
    return `<button type="button" data-item-key="${esc(itemKey(item))}"><i></i><strong>${esc(item.title)}</strong>${item.community ? `<em>${esc(item.community)}</em>` : ""}<span class="list-meta">${esc(item.district || "區域待確認")}・${numberText(item.price)} 萬${unitPrice}${summary ? `<small class="list-metric">${esc(summary)}</small>` : ""}</span></button>`;
  }).join("") || "<p>沒有符合目前篩選的房源。</p>";
  const unlocated = state.visible.filter(item => !DISTRICT_CENTERS[item.district]).length;
  document.querySelector("#map-count").textContent = `顯示 ${state.visible.length} 筆${STATUS_META[state.status].label}${unlocated ? `（${unlocated} 筆無定位）` : ''}`;
}
function focusMarker(entry, zoom = 14) {
  const meta = STATUS_META[state.status];
  state.markers.forEach(({marker}) => {
    marker.closeTooltip();
    marker.setStyle({ radius:8, weight:2, color:"#fff", fillColor:meta.color, fillOpacity:.92 });
  });
  entry.marker.setStyle({ radius:11, weight:3, color:"#17392b", fillColor:meta.color, fillOpacity:1 });
  entry.marker.bringToFront();
  state.map.flyTo(entry.marker.getLatLng(), Math.max(state.map.getZoom(), zoom), { duration:.38 });
  renderDetail(entry.item);
  entry.marker.openTooltip();
}
function renderMarkers() {
  state.markers.forEach(({marker}) => marker.remove());
  const order = new Map();
  state.markers = state.visible.map((item) => {
    const position = stablePosition(item, order);
    if (!position) return null;
    const marker = L.circleMarker(position, { radius:8, weight:2, color:"#fff", fillColor:STATUS_META[state.status].color, fillOpacity:.92 }).addTo(state.map);
    marker.bindTooltip(`${esc(item.title)}・${numberText(item.price)} 萬`, { direction:"top" });
    const entry = { marker, item };
    marker.on("click", () => focusMarker(entry, 14));
    return entry;
  }).filter(Boolean);
  const points = state.markers.map(({marker}) => marker.getLatLng());
  if (points.length) state.map.fitBounds(L.latLngBounds(points).pad(.14), { maxZoom:12 });
}
function applyFilters() {
  const district = document.querySelector("#map-district").value;
  const query = document.querySelector("#map-search").value.trim().toLowerCase();
  const failure = document.querySelector("#map-failure").value;
  const baths = document.querySelector('#map-baths').value;
  state.visible = sortedItems(state.items.filter((item) => (!district || item.district === district) && (!failure || failureCategories(item).includes(failure)) && (!baths || (baths === 'unknown' ? item.baths == null : baths === '2plus' ? Number(item.baths) >= 2 : Number(item.baths) === 1)) && (!query || [item.id,item.title,item.community,item.district,item.source].some((value) => String(value || "").toLowerCase().includes(query)))));
  renderList(); renderMarkers();
  const selected = state.visible.find(item => itemKey(item) === state.selected) || state.visible[0];
  if (selected) renderDetail(selected);
  else {
    state.selected = null;
    document.querySelector('#map-detail').innerHTML = '<div class="empty-detail"><b>沒有符合篩選的房源</b><span>請調整行政區、衛浴或搜尋文字。</span></div>';
  }
}
function loadStatus(status) {
  state.status = status;
  const seen = new Set();
  const sourceItems = status === "favorites" ? (state.payload.favorites || []) : (state.payload.groups?.[status] || []);
  state.items = sourceItems.filter((item) => item.profile === profile).filter((item) => { const key=itemKey(item); if(seen.has(key)) return false; seen.add(key); return true; });
  state.selected = null;
  document.querySelectorAll("#map-status-tabs button").forEach((button) => button.classList.toggle("active", button.dataset.status === status));
  document.querySelector("#map-title").textContent = `${PROFILE_LABELS[profile] || profile}・${STATUS_META[status].label}房源地圖`;
  const url = new URL(window.location.href);
  url.searchParams.set("profile", profile);
  url.searchParams.set("status", status);
  window.history.replaceState(null, "", url);
  const districtSelect = document.querySelector("#map-district");
  const previousDistrict = districtSelect.value;
  districtSelect.innerHTML = '<option value="">全部行政區</option>';
  const districts = [...new Set(state.items.map((item) => item.district).filter(Boolean))].sort((a,b) => a.localeCompare(b,"zh-TW"));
  districtSelect.insertAdjacentHTML("beforeend", districts.map((district) => `<option value="${esc(district)}">${esc(district)}</option>`).join(""));
  if (districts.includes(previousDistrict)) districtSelect.value = previousDistrict;
  const failureWrap = document.querySelector("#map-failure-wrap");
  const failureSelect = document.querySelector("#map-failure");
  failureWrap.hidden = !["near_match", "rejected"].includes(status);
  const counts = new Map();
  state.items.forEach((item) => failureCategories(item).forEach((category) => counts.set(category, (counts.get(category) || 0) + 1)));
  failureSelect.innerHTML = '<option value="">全部原因</option>' + [...counts.entries()].sort((a,b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-TW")).map(([category,count]) => `<option value="${esc(category)}">${esc(category)}（${count}）</option>`).join("");
  document.querySelector("#map-sort").value = ["near_match", "rejected"].includes(status) ? "failures-asc" : "metric-desc";
  if (initialFilters.size) {
    for (const key of ['district','baths','sort','search','failure']) {
      const value = initialFilters.get(key);
      const element = document.getElementById(`map-${key}`);
      if (value != null && element && (element.tagName !== 'SELECT' || [...element.options].some(o => o.value === value))) element.value = value;
    }
    [...initialFilters.keys()].forEach(key => initialFilters.delete(key));
  }
  applyFilters();
}
function selectProfile(nextProfile) {
  profile = PROFILE_LABELS[nextProfile] ? nextProfile : "大樓公寓華廈";
  document.querySelectorAll("#map-profile-tabs button").forEach((button) => {
    const active = button.dataset.profile === profile;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  document.querySelectorAll("#map-status-tabs button").forEach((button) => {
    const sourceItems = button.dataset.status === "favorites" ? (state.payload.favorites || []) : (state.payload.groups?.[button.dataset.status] || []);
    button.querySelector("span").textContent = sourceItems.filter((item) => item.profile === profile).length;
  });
  loadStatus(state.status);
}
document.querySelector("#map-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-item-key]"); if (!button) return;
  const match = state.markers.find(({item}) => itemKey(item) === button.dataset.itemKey);
  if (!match) {
    const item = state.visible.find(item => itemKey(item) === button.dataset.itemKey);
    if (item) renderDetail(item);
    return;
  }
  focusMarker(match, 15);
});
document.querySelector("#map-district").addEventListener("change", applyFilters);
document.querySelector('#map-baths').addEventListener('change', applyFilters);
document.querySelector("#map-search").addEventListener("input", applyFilters);
document.querySelector("#map-sort").addEventListener("change", applyFilters);
document.querySelector("#map-failure").addEventListener("change", applyFilters);
document.querySelector("#map-status-tabs").addEventListener("click", (event) => {
  const button = event.target.closest("[data-status]");
  if (button) loadStatus(button.dataset.status);
});
document.querySelector("#map-profile-tabs").addEventListener("click", (event) => {
  const button = event.target.closest("[data-profile]");
  if (button && state.payload) selectProfile(button.dataset.profile);
});

fetch("/api/results").then((response) => response.ok ? response.json() : Promise.reject(new Error("讀取房源失敗"))).then((payload) => {
  state.payload = payload;
  state.map = L.map("property-map", { zoomControl:true }).setView([22.72,120.34],10);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom:18, attribution:"&copy; OpenStreetMap contributors" }).addTo(state.map);
  state.status = requestedStatus;
  selectProfile(profile);
}).catch((error) => { document.querySelector("#map-count").textContent = error.message; });
