function availabilityTrackingV12(item) {
  if (!item.is_favorite || !item.availability_status) return "";
  const labels = {
    available: "刊登中",
    removed: "已下架",
    unknown: "查核失敗",
  };
  const label = labels[item.availability_status] || "待查核";
  return `<div class="favorite-availability availability-${escapeHtml(item.availability_status)}">
    <strong>${escapeHtml(label)}</strong>
    <span>${escapeHtml(item.availability_reason || "")}</span>
    <small>查核：${escapeHtml(dateText(item.availability_checked_at))}</small>
  </div>`;
}

const previousListingCardV12 = listingCard;
listingCard = function listingCardV12(item) {
  let html = previousListingCardV12(item);
  if (!item.is_favorite || !item.availability_status) return html;
  html = html.replace("<h2>", `${availabilityTrackingV12(item)}<h2>`);
  if (item.availability_status === "removed") {
    html = html.replace("listing-card favorite-card", "listing-card favorite-card delisted-card");
    html = html.replace(
      /<button class="favorite-toggle active"([^>]*)>[^<]*<\/button>/,
      '<button class="favorite-toggle active remove-delisted-favorite"$1>移除收藏</button>'
    );
  }
  return html;
};

const previousRenderInsightV12 = renderInsight;
renderInsight = function renderInsightV12() {
  previousRenderInsightV12();
  const diagnostic = state.payload?.search_diagnostics?.[state.activeProfile];
  const audit = diagnostic?.favorite_availability;
  if (!audit) return;
  const box = document.querySelector("#goal-insight");
  if (audit.error) {
    box.insertAdjacentHTML("beforeend", '<p class="favorite-audit-summary audit-warning">收藏網址查核未完成，原收藏狀態已保留。</p>');
    return;
  }
  const total = Number(audit.available || 0) + Number(audit.removed || 0) + Number(audit.unknown || 0);
  box.insertAdjacentHTML("beforeend", `<p class="favorite-audit-summary">
    收藏查核 ${total} 筆：本輪找到 ${Number(audit.current || 0)} 筆、
    開啟網址 ${Number(audit.url_checks || 0)} 筆、已下架 ${Number(audit.removed || 0)} 筆、查核失敗 ${Number(audit.unknown || 0)} 筆
    ${audit.duration_seconds != null ? `・額外耗時 ${escapeHtml(formatDuration(audit.duration_seconds))}` : ""}
  </p>`);
};
