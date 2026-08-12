state.favoriteAvailabilityFilter = "all";

const favoriteFilterBarV13 = document.createElement("section");
favoriteFilterBarV13.id = "favorite-status-filters";
favoriteFilterBarV13.className = "favorite-status-filters";
favoriteFilterBarV13.hidden = true;
document.querySelector("#results").insertAdjacentElement("beforebegin", favoriteFilterBarV13);

function favoriteStatusV13(item) {
  return item.availability_status || "pending";
}

function renderFavoriteFiltersV13() {
  const favorites = state.payload?.favorites || [];
  const counts = { all: favorites.length, available: 0, removed: 0, unknown: 0, pending: 0 };
  favorites.forEach((item) => { counts[favoriteStatusV13(item)] += 1; });
  const labels = [
    ["all", "全部"], ["available", "刊登中"], ["removed", "已下架"],
    ["unknown", "查核失敗"], ["pending", "待查核"],
  ];
  favoriteFilterBarV13.hidden = state.activeStatus !== "favorites";
  favoriteFilterBarV13.innerHTML = labels.map(([value, label]) =>
    `<button type="button" data-favorite-status="${value}" class="${state.favoriteAvailabilityFilter === value ? "active" : ""}" aria-pressed="${state.favoriteAvailabilityFilter === value}">${label} <b>${counts[value]}</b></button>`
  ).join("");
}

const previousProfileItemsV13 = profileItems;
profileItems = function profileItemsV13(profile, status) {
  const items = previousProfileItemsV13(profile, status);
  if (status !== "favorites" || state.favoriteAvailabilityFilter === "all") return items;
  return items.filter((item) => favoriteStatusV13(item) === state.favoriteAvailabilityFilter);
};

function favoriteNoteV13(item) {
  if (!item.is_favorite) return "";
  const note = item.favorite_note || "";
  return `<details class="favorite-note" ${note ? "open" : ""}>
    <summary>${note ? "我的備註" : "＋ 新增備註"}</summary>
    <textarea maxlength="500" rows="3" placeholder="例如：地點很好、屋況需整理、議價目標 1,050 萬">${escapeHtml(note)}</textarea>
    <div><small><span class="favorite-note-count">${note.length}</span>/500</small><button type="button" class="favorite-note-save" data-source="${escapeHtml(item.source || "591")}" data-listing-id="${escapeHtml(item.id)}">儲存備註</button></div>
  </details>`;
}

function availabilityHistoryV13(item) {
  if (item.availability_status !== "removed") return "";
  const history = (item.availability_history || []).slice().reverse();
  return `<div class="delisted-history">
    <strong>下架確認：${escapeHtml(dateText(item.removed_at))}</strong>
    <span>最後價格：${item.price != null ? `${escapeHtml(item.price)} 萬` : "待確認"}</span>
    ${history.length ? `<details><summary>查看狀態紀錄（${history.length}）</summary><ul>${history.map((entry) => `<li>${escapeHtml(dateText(entry.checked_at))}・${escapeHtml(entry.reason || "狀態更新")}</li>`).join("")}</ul></details>` : ""}
  </div>`;
}

const previousListingCardV13 = listingCard;
listingCard = function listingCardV13(item) {
  let html = previousListingCardV13(item);
  if (!item.is_favorite) return html;
  html = html.replace("<h2>", `${availabilityHistoryV13(item)}${favoriteNoteV13(item)}<h2>`);
  return html;
};

const previousRenderNavigationV13 = renderNavigation;
renderNavigation = function renderNavigationV13() {
  previousRenderNavigationV13();
  renderFavoriteFiltersV13();
};

favoriteFilterBarV13.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-favorite-status]");
  if (!button) return;
  state.favoriteAvailabilityFilter = button.dataset.favoriteStatus;
  renderFavoriteFiltersV13();
  renderResults();
});

document.querySelector("#results").addEventListener("input", (event) => {
  const textarea = event.target.closest(".favorite-note textarea");
  if (textarea) textarea.closest(".favorite-note").querySelector(".favorite-note-count").textContent = textarea.value.length;
});

document.querySelector("#results").addEventListener("click", async (event) => {
  const button = event.target.closest("button.favorite-note-save");
  if (!button) return;
  const noteBox = button.closest(".favorite-note");
  button.disabled = true;
  try {
    const response = await fetch("/api/favorites/note", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: button.dataset.source, id: button.dataset.listingId, note: noteBox.querySelector("textarea").value }),
    });
    state.payload = await readJsonResponse(response, "儲存收藏備註失敗");
    renderNavigation();
    renderResults();
    document.querySelector("#status-message").textContent = "收藏備註已儲存";
  } catch (error) {
    document.querySelector("#status-message").textContent = `儲存收藏備註失敗：${error.message}`;
    button.disabled = false;
  }
});
