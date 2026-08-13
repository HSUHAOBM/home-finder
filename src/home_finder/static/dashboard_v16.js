favoriteTrackingV8 = function favoriteTrackingV16(item) {
  if (!item.is_favorite) return "";
  const changes = item.favorite_changes || [];
  const history = item.favorite_change_history || [];
  const availability = item.availability_status || "pending";
  const labels = { available: "刊登中", removed: "已下架", unknown: "查核失敗", pending: "待查核" };
  const stateLabel = labels[availability] || "待查核";
  const changeLabel = changes.length ? `資料更新 ${changes.length} 項` : "無新變動";
  const historyHtml = history.length > 1 ? `<details class="favorite-change-history">
    <summary>查看過去 ${history.length} 次變動</summary>
    ${history.slice(0, -1).reverse().map((entry) => `<div class="favorite-change-event"><strong>${escapeHtml(dateText(entry.detected_at))}</strong><ul>${(entry.changes || []).map((change) => `<li>${escapeHtml(change)}</li>`).join("")}</ul></div>`).join("")}
  </details>` : "";
  return `<details class="favorite-overview availability-${escapeHtml(availability)}" ${availability === "removed" ? "open" : ""}>
    <summary><strong>${escapeHtml(stateLabel)}</strong><b class="${changes.length ? "has-change" : ""}">${escapeHtml(changeLabel)}</b><small>${escapeHtml(dateText(item.availability_checked_at || item.favorite_last_seen_at))}</small></summary>
    <div class="favorite-overview-detail">
      <span>${escapeHtml(item.availability_reason || (item.favorite_is_current ? "本次搜尋仍有出現" : "保留收藏快照"))}</span>
      <span>收藏：${escapeHtml(dateText(item.favorite_saved_at))}・最近看到：${escapeHtml(dateText(item.favorite_last_seen_at))}</span>
      ${changes.length ? `<ul>${changes.map((change) => `<li>${escapeHtml(change)}</li>`).join("")}</ul>` : ""}
      ${historyHtml}
    </div>
  </details>`;
};

availabilityTrackingV12 = function availabilityTrackingV16() { return ""; };

favoriteNoteV13 = function favoriteNoteV16(item) {
  if (!item.is_favorite) return "";
  const note = item.favorite_note || "";
  return `<details class="favorite-note favorite-note-compact">
    <summary>${note ? "備註已填" : "＋ 備註"}</summary>
    <textarea maxlength="500" rows="3" placeholder="例如：地點很好、屋況需整理、議價目標 1,050 萬">${escapeHtml(note)}</textarea>
    <div><small><span class="favorite-note-count">${note.length}</span>/500</small><button type="button" class="favorite-note-save" data-source="${escapeHtml(item.source || "591")}" data-listing-id="${escapeHtml(item.id)}">儲存備註</button></div>
  </details>`;
};

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
      <button type="button" data-months="120">近 10 年</button>
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
  const historyNotice = months === 120
    ? "近 10 年首次查詢需下載約 40 季資料，可能需要數分鐘。"
    : months === 60
      ? "近 5 年首次查詢需下載約 20 季資料，時間會比較久。"
      : "首次查詢可能需要約 1 分鐘。";
  results.innerHTML = `<div class="real-price-loading">正在讀取內政部官方資料……${historyNotice}</div>`;
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
