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

function listingAvailabilityV16(item) {
  const labels = { available: "刊登中", removed: "已下架", unknown: "查核失敗" };
  const status = listingAvailabilityState(item);
  const checked = status !== "pending";
  if (!checked) return "";
  const result = `<strong class="status-${escapeHtml(status)}">${escapeHtml(labels[status] || "查核失敗")}</strong><span>${escapeHtml(item.url_availability_reason || item.availability_reason || "")}</span><small>${escapeHtml(dateText(item.url_availability_checked_at || item.availability_checked_at))}</small>`;
  return `<div class="listing-availability" data-source="${escapeHtml(item.source || "591")}" data-listing-id="${escapeHtml(item.id)}">
    ${result}
  </div>`;
}

function listingDeleteButtonV16(item) {
  return `<button type="button" class="listing-delete" data-source="${escapeHtml(item.source || "591")}" data-listing-id="${escapeHtml(item.id)}" data-availability="${escapeHtml(listingAvailabilityState(item))}" aria-label="刪除這張房源卡" title="刪除這張房源卡">×</button>`;
}

const previousListingCardV16 = listingCard;
listingCard = function listingCardV16(item) {
  let html = previousListingCardV16(item);
  const showFavoriteTools = state.activeStatus === "favorites";
  const availability = showFavoriteTools ? "" : listingAvailabilityV16(item);
  if (availability) html = html.replace("<h2>", `${availability}<h2>`);
  if (item.broker_watch_alert) {
    const alert = item.broker_watch_alert;
    const count = Number(alert.incident_count || 0);
    const warning = `<aside class="broker-watch-alert"><strong>房仲刊登提醒</strong><span>${escapeHtml(alert.broker_name)} 過去有 ${count} 筆建物型態與樓層資料矛盾，請逐項查證。</span></aside>`;
    html = html.replace("<h2>", `${warning}<h2>`);
  }
  if (item.is_favorite && showFavoriteTools) html = html.replace("<h2>", `${realPriceButtonV16(item)}<h2>`);
  const template = document.createElement("template");
  template.innerHTML = html.trim();
  const card = template.content.querySelector(".listing-card");
  const link = card?.querySelector(".listing-link");
  if (!card || !link) return html;
  card.querySelector(".card-top")?.insertAdjacentHTML("beforeend", listingDeleteButtonV16(item));
  const title = card.querySelector(":scope > h2");
  const cardTop = card.querySelector(":scope > .card-top");
  if (title && cardTop) card.insertBefore(title, cardTop);
  const actions = document.createElement("section");
  actions.className = "card-actions";
  const favoriteToggle = card.querySelector(":scope > .favorite-toggle");
  link.insertAdjacentElement("beforebegin", actions);
  if (favoriteToggle) actions.appendChild(favoriteToggle);
  actions.appendChild(link);
  if (item.is_favorite && showFavoriteTools) {
    const management = document.createElement("section");
    management.className = "favorite-card-management";
    const overview = card.querySelector(".favorite-overview");
    const tools = document.createElement("div");
    tools.className = "favorite-card-tools";
    [".favorite-note-compact", ".favorite-compare-toggle", ".real-price-entry"]
      .forEach((selector) => {
        const element = card.querySelector(selector);
        if (element) tools.appendChild(element);
      });
    if (overview) management.appendChild(overview);
    management.appendChild(tools);
    actions.insertAdjacentElement("afterend", management);
  } else {
    [".favorite-overview", ".favorite-note-compact", ".favorite-compare-toggle", ".real-price-entry"]
      .forEach((selector) => card.querySelector(selector)?.remove());
  }
  const supplemental = document.createElement("footer");
  supplemental.className = "listing-supplemental";
  const statusNotes = document.createElement("ul");
  statusNotes.className = "listing-status-notes";
  card.querySelectorAll(":scope > .notes > li").forEach((note) => {
    if (note.textContent.includes("本次搜尋未再次找到")) statusNotes.appendChild(note);
  });
  if (statusNotes.childElementCount) supplemental.appendChild(statusNotes);
  const notes = card.querySelector(":scope > .notes");
  if (notes && !notes.childElementCount) notes.remove();
  [".broker-watch-alert", ".tracking-row", ".change-details", ".listing-availability"]
    .forEach((selector) => {
      const element = card.querySelector(selector);
      if (element) supplemental.appendChild(element);
    });
  if (supplemental.childElementCount) card.appendChild(supplemental);
  return card.outerHTML;
};

function realPriceNumberV16(value, suffix = "") {
  return value == null ? "待確認" : `${Number(value).toLocaleString("zh-TW", { maximumFractionDigits: 2 })}${suffix}`;
}

function realPriceWorkspaceV16(item) {
  const floor = item.floor == null ? "待確認" : `${realPriceNumberV16(item.floor)} / ${realPriceNumberV16(item.total_floors)} 樓`;
  const layout = item.rooms == null ? "待確認" : `${realPriceNumberV16(item.rooms)} 房・${realPriceNumberV16(item.baths)} 衛`;
  return `<section class="real-price-workspace" data-source="${escapeHtml(item.source || "591")}" data-listing-id="${escapeHtml(item.id)}">
    <span class="section-label">OFFICIAL REAL PRICE</span>
    <h2>${escapeHtml(item.community || "社區實價登錄")}</h2>
    <p>${escapeHtml(item.district || "")} ${escapeHtml(item.address || "地址待確認")}</p>
    <section class="real-price-listing-reference" aria-label="目前收藏房源">
      <header><strong>目前收藏房源</strong><span>實價資料將與這張房卡比較</span></header>
      <div>
        <span><small>開價</small><b>${realPriceNumberV16(item.price, " 萬")}</b></span>
        <span><small>權狀坪數</small><b>${realPriceNumberV16(item.total_area, " 坪")}</b></span>
        <span><small>樓層</small><b>${escapeHtml(floor)}</b></span>
        <span><small>屋齡</small><b>${realPriceNumberV16(item.age, " 年")}</b></span>
        <span><small>格局</small><b>${escapeHtml(layout)}</b></span>
        <span><small>車位</small><b>${escapeHtml(item.parking || "待確認")}</b></span>
      </div>
    </section>
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
    <h3>最相近成交</h3><p>相似度只用來協助排序；「可能為本收藏房」仍需以完整門牌或謄本確認。<details class="similarity-help"><summary>相似度怎麼算？</summary><span>社區／門牌 20%、權狀坪數 25%、樓層 20%、總樓層 10%、屋齡 10%、房數 8%、車位 4%、建物型態 3%；缺少的欄位不列入分母。歷史成交屋齡會依完工年換算至目前再比較。門牌範圍、樓層完全相同，且坪數差在 1 坪或 3% 內、總分達 90%，才標示「可能為本收藏房」。</span></details></p>
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
  const clearRemoved = event.target.closest(".clear-removed-page");
  const clearCategory = event.target.closest(".clear-current-category");
  const deleteButton = event.target.closest(".listing-delete");
  if (clearRemoved || clearCategory || deleteButton) {
    const buttons = clearRemoved
      ? [...document.querySelectorAll("#results .listing-delete[data-availability='removed']")]
      : (deleteButton ? [deleteButton] : []);
    const categoryCards = clearCategory ? profileItems(state.activeProfile, state.activeStatus) : [];
    const items = clearCategory
      ? categoryCards.map((item) => ({ source: item.source || "591", id: item.id }))
      : buttons.map((button) => ({ source: button.dataset.source, id: button.dataset.listingId }));
    if (!items.length) return;
    const message = clearCategory
      ? `確定清除「差強人意」全部 ${items.length} 筆房源？完全符合、可接受、待確認、已排除與收藏都不會受影響。`
      : (clearRemoved
        ? `確定清除此頁 ${items.length} 筆已下架房源？其他分類不會受影響。`
        : "確定刪除這張房源卡？若未來重新抓到，會標示為重新上架。");
    if (!window.confirm(message)) return;
    if (clearCategory) clearCategory.disabled = true;
    buttons.forEach((button) => { button.disabled = true; });
    fetch("/api/listings/delete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items,
        profile: state.activeProfile,
        category: state.activeStatus,
        removed_only: Boolean(clearRemoved),
        clear_category: Boolean(clearCategory),
      }),
    }).then((response) => readJsonResponse(response, "刪除房源失敗"))
      .then((result) => {
        state.payload = result.results;
        renderNavigation();
        renderResults();
        document.querySelector("#status-message").textContent = `已刪除 ${result.deleted} 筆房源；歷史紀錄已保留。`;
      }).catch((error) => {
        document.querySelector("#status-message").textContent = `刪除房源失敗：${error.message}`;
        if (clearCategory) clearCategory.disabled = false;
        buttons.forEach((button) => { button.disabled = false; });
      });
    return;
  }
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

state.houseTypeFilter = "";
const houseTypeFiltersV16 = document.createElement("section");
houseTypeFiltersV16.id = "house-type-filters";
houseTypeFiltersV16.className = "house-type-filters";
houseTypeFiltersV16.hidden = true;
houseTypeFiltersV16.innerHTML = `<span>建物型態</span><div>
  <button type="button" data-house-type="" class="active">全部</button>
  <button type="button" data-house-type="透天厝">透天</button>
  <button type="button" data-house-type="別墅">別墅</button>
</div>`;
document.querySelector("#results").insertAdjacentElement("beforebegin", houseTypeFiltersV16);

const previousRenderResultsV16 = renderResults;
renderResults = function renderResultsWithHouseTypeV16() {
  const filtering = state.activeProfile === "透天別墅"
    && state.houseTypeFilter && !String(state.resultQuery || "").trim();
  const originalProfileItems = profileItems;
  if (filtering) {
    profileItems = function filteredHouseProfileItemsV16(profile, status) {
      const items = originalProfileItems(profile, status);
      return profile === "透天別墅"
        ? items.filter((item) => item.property_type === state.houseTypeFilter)
        : items;
    };
  }
  try { previousRenderResultsV16(); } finally { profileItems = originalProfileItems; }
  houseTypeFiltersV16.hidden = state.activeProfile !== "透天別墅"
    || Boolean(String(state.resultQuery || "").trim());
  houseTypeFiltersV16.querySelectorAll("button").forEach((button) => {
    const active = button.dataset.houseType === state.houseTypeFilter;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
};

houseTypeFiltersV16.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-house-type]");
  if (!button) return;
  state.houseTypeFilter = button.dataset.houseType;
  renderResults();
});

document.querySelectorAll(".goal-card").forEach((card) => {
  card.addEventListener("click", () => {
    if (card.dataset.profile !== "透天別墅") state.houseTypeFilter = "";
    renderResults();
  });
});
