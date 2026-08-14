const previousCommuteLinksV15 = commuteLinksV14;
commuteLinksV14 = function commuteLinksV15(item) {
  const origin = fullAddressV14(item);
  const links = previousCommuteLinksV15(item);
  const rawAddress = String(item.address || "").trim();
  const roadFallback = rawAddress
    ? (rawAddress.startsWith("高雄市") ? rawAddress : `高雄市${item.district || ""}${rawAddress}`)
    : "";
  if (!origin) return links;
  return `<div class="commute-estimate-box" data-commute-origin="${escapeHtml(origin)}" data-commute-fallback="${escapeHtml(roadFallback)}">
    <button class="commute-estimate-button" type="button">估算通勤時間</button>
    <small>OSRM 一般開車估算，不含即時路況；機車僅供參考。</small>
    <div class="commute-estimate-results"></div>
  </div>${links}`;
};

document.querySelector("#favorite-workspace-content").addEventListener("click", async (event) => {
  const button = event.target.closest(".commute-estimate-button");
  if (!button) return;
  const box = button.closest(".commute-estimate-box");
  const results = box.querySelector(".commute-estimate-results");
  const consented = sessionStorage.getItem("commute-estimate-consent-v15") === "yes";
  if (!consented) {
    const approved = window.confirm("通勤估算會將房源約略地址、義大醫院與住家地址傳送至 OpenStreetMap Nominatim 及 OSRM 公開服務。是否同意本次瀏覽期間使用？");
    if (!approved) return;
    sessionStorage.setItem("commute-estimate-consent-v15", "yes");
  }
  button.disabled = true;
  button.textContent = "估算中…";
  try {
    const response = await fetch("/api/commute-estimate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        origin: box.dataset.commuteOrigin,
        origin_fallbacks: box.dataset.commuteFallback ? [box.dataset.commuteFallback] : [],
      }),
    });
    const payload = await readJsonResponse(response, "通勤估算失敗");
    const resolved = payload.resolved_origin && payload.resolved_origin !== payload.origin
      ? `<small>社區名稱無法定位，已改用 ${escapeHtml(payload.resolved_origin)} 估算。</small>` : "";
    results.innerHTML = `${resolved}${payload.estimates.map((item) => `<div><strong>${escapeHtml(item.name)}</strong><span>約 ${escapeHtml(item.minutes)} 分鐘・${escapeHtml(item.distance_km)} km</span>${item.resolved_address && item.resolved_address !== item.address ? `<small>已改用 ${escapeHtml(item.resolved_address)} 定位</small>` : ""}</div>`).join("")}`;
    button.textContent = "重新顯示估算";
  } catch (error) {
    results.innerHTML = `<p>${escapeHtml(error.message)}；仍可使用下方 Google Maps 路線。</p>`;
    button.textContent = "重新估算";
  } finally { button.disabled = false; }
});
