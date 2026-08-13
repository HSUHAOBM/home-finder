function realPriceButtonV16(item) {
  if (!item.is_favorite) return "";
  const disabled = !item.district || !item.address;
  return `<div class="real-price-entry">
    <button class="real-price-open" type="button"
      data-source="${escapeHtml(item.source || "591")}" data-listing-id="${escapeHtml(item.id)}"
      ${disabled ? "disabled" : ""} title="${disabled ? "缺少行政區或地址，無法比對" : "查詢最近一年官方實價登錄"}">
      社區實價 <span aria-hidden="true">›</span>
    </button>
    <small>${escapeHtml(item.community || item.address || "社區待確認")}</small>
  </div>`;
}

const previousListingCardV16 = listingCard;
listingCard = function listingCardV16(item) {
  let html = previousListingCardV16(item);
  if (item.is_favorite) html = html.replace("<h2>", `${realPriceButtonV16(item)}<h2>`);
  return html;
};

function realPriceNumberV16(value, suffix = "") {
  return value == null ? "待確認" : `${Number(value).toLocaleString("zh-TW", { maximumFractionDigits: 2 })}${suffix}`;
}

function realPriceWorkspaceV16(item) {
  return `<section class="real-price-workspace" data-source="${escapeHtml(item.source || "591")}" data-listing-id="${escapeHtml(item.id)}">
    <span class="section-label">OFFICIAL REAL PRICE</span>
    <h2>${escapeHtml(item.community || "社區實價登錄")}</h2>
    <p>${escapeHtml(item.district || "")} ${escapeHtml(item.address || "地址待確認")}</p>
    <div class="real-price-period" role="group" aria-label="查詢期間">
      <button type="button" data-months="6">近 6 個月</button>
      <button type="button" data-months="12" class="active">近 1 年</button>
      <button type="button" data-months="60">近 5 年</button>
    </div>
    <div class="real-price-results"><div class="real-price-loading">正在讀取內政部官方資料……首次查詢需要下載季度資料。</div></div>
  </section>`;
}

function renderRealPriceV16(box, payload) {
  const results = box.querySelector(".real-price-results");
  const summary = payload.summary;
  const levelClass = payload.match_level === "address" ? "address" : payload.match_level === "road" ? "road" : "none";
  const askingUnit = payload.listing_unit_price;
  const comparison = summary && askingUnit != null
    ? Math.round((askingUnit - summary.median_unit_price) * 100) / 100 : null;
  const summaryHtml = summary ? `<div class="real-price-summary">
      <div><small>成交筆數</small><strong>${summary.count} 筆</strong></div>
      <div><small>單價中位數</small><strong>${realPriceNumberV16(summary.median_unit_price, " 萬／坪")}</strong></div>
      <div><small>單價範圍</small><strong>${realPriceNumberV16(summary.min_unit_price)}～${realPriceNumberV16(summary.max_unit_price)} 萬／坪</strong></div>
      <div><small>最近成交</small><strong>${escapeHtml(summary.latest_date)}</strong></div>
      <div><small>房源開價單價</small><strong>${realPriceNumberV16(askingUnit, " 萬／坪")}</strong></div>
      <div><small>與中位數比較</small><strong>${comparison == null ? "待確認" : `${comparison >= 0 ? "+" : ""}${comparison} 萬／坪`}</strong></div>
    </div>` : `<div class="real-price-empty"><strong>最近期間查無相近成交</strong><span>可前往官方網站自行調整條件。</span></div>`;
  const closestHtml = (payload.closest_matches || []).length ? `<section class="closest-matches">
    <h3>最相近成交</h3><p>相似度只用來協助排序，不代表已確認為同一戶。</p>
    <div>${payload.closest_matches.map((row, index) => `<article class="closest-match ${index === 0 ? "best" : ""}">
      <header><span>${index === 0 ? "最接近" : `第 ${index + 1} 名`}</span><strong>${escapeHtml(row.similarity_label)} ${row.similarity_score}%</strong></header>
      <b>${escapeHtml(row.date)}．${escapeHtml(row.address)}</b>
      <div>${realPriceNumberV16(row.total_price_wan, " 萬")}．${realPriceNumberV16(row.unit_price_wan_ping, " 萬／坪")}．${realPriceNumberV16(row.area_ping, " 坪")}</div>
      <small class="similarity-reasons">符合：${escapeHtml((row.similarity_reasons || []).join("、") || "同路段")}</small>
      ${(row.differences || []).length ? `<small class="similarity-differences">差異：${escapeHtml(row.differences.join("、"))}</small>` : ""}
    </article>`).join("")}</div>
  </section>` : "";
  const rows = (payload.transactions || []).map((row) => `<tr>
    <td><strong>${row.similarity_score}%</strong><small>${escapeHtml(row.similarity_label)}</small></td>
    <td>${escapeHtml(row.date)}</td><td>${escapeHtml(row.address)}</td>
    <td>${realPriceNumberV16(row.total_price_wan, " 萬")}</td>
    <td>${realPriceNumberV16(row.unit_price_wan_ping, " 萬／坪")}</td>
    <td>${realPriceNumberV16(row.area_ping, " 坪")}</td>
    <td>${escapeHtml(row.floor || "待確認")}</td><td>${escapeHtml(row.parking || "無")}</td>
  </tr>`).join("");
  results.innerHTML = `<div class="real-price-match ${levelClass}"><strong>${escapeHtml(payload.match_label)}．${escapeHtml(payload.comparison_scope || "")}</strong><span>${escapeHtml(payload.notice)}</span></div>
    ${summaryHtml}
    ${closestHtml}
    ${rows ? `<div class="real-price-table-wrap"><table><thead><tr><th>相似度</th><th>交易日</th><th>門牌</th><th>總價</th><th>單價</th><th>坪數</th><th>樓層</th><th>車位</th></tr></thead><tbody>${rows}</tbody></table></div>` : ""}
    <footer>資料季度：${payload.seasons.map(escapeHtml).join("、")}．<a href="${safeUrl(payload.source_url)}" target="_blank" rel="noopener">開啟內政部官方查詢</a></footer>`;
}

async function loadRealPriceV16(box, months) {
  const results = box.querySelector(".real-price-results");
  results.innerHTML = `<div class="real-price-loading">正在讀取內政部官方資料……${months === 60 ? "近 5 年首次查詢需下載約 20 季資料，時間會比較久。" : "首次查詢可能需要約 1 分鐘。"}</div>`;
  box.querySelectorAll("[data-months]").forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.months) === months);
    button.disabled = true;
  });
  try {
    const response = await fetch("/api/favorites/real-price", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: box.dataset.source, id: box.dataset.listingId, months }),
    });
    renderRealPriceV16(box, await readJsonResponse(response, "實價登錄查詢失敗"));
  } catch (error) {
    results.innerHTML = `<div class="real-price-error">${escapeHtml(error.message)}</div>`;
  } finally {
    box.querySelectorAll("[data-months]").forEach((button) => { button.disabled = false; });
  }
}

document.querySelector("#results").addEventListener("click", (event) => {
  const button = event.target.closest(".real-price-open");
  if (!button) return;
  const item = (state.payload?.favorites || []).find((favorite) =>
    String(favorite.source || "591") === button.dataset.source && String(favorite.id) === button.dataset.listingId);
  if (!item) return;
  document.querySelector("#favorite-workspace-content").innerHTML = realPriceWorkspaceV16(item);
  workspaceV14.showModal();
  loadRealPriceV16(document.querySelector(".real-price-workspace"), 12);
});

document.querySelector("#favorite-workspace-content").addEventListener("click", (event) => {
  const button = event.target.closest(".real-price-period [data-months]");
  if (button) loadRealPriceV16(button.closest(".real-price-workspace"), Number(button.dataset.months));
});
