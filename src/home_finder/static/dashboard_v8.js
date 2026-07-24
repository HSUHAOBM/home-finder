const favoritesTabV8 = document.querySelector('[data-status="rejected"]');
favoritesTabV8.insertAdjacentHTML(
  "afterend",
  '<button class="tab favorite-tab" type="button" data-status="favorites">我的收藏 <span id="tab-favorites">0</span></button>'
);

const resultSortV8 = document.querySelector("#result-sort");
resultSortV8.querySelector('[value="newest"]').insertAdjacentHTML(
  "beforebegin",
  '<option value="favorite_saved" hidden>最近收藏</option>'
);

const previousProfileItemsV8 = profileItems;
profileItems = function profileItemsV8(profile, status) {
  if (status === "favorites") return state.payload ? state.payload.favorites || [] : [];
  return previousProfileItemsV8(profile, status);
};

const previousSelectFirstNonEmptyStatusV8 = selectFirstNonEmptyStatusV7;
selectFirstNonEmptyStatusV7 = function selectFirstNonEmptyStatusV8() {
  if (state.activeStatus === "favorites") return;
  previousSelectFirstNonEmptyStatusV8();
};

const previousSortItemsV8 = sortItemsV7;
sortItemsV7 = function sortItemsV8(items) {
  if (state.activeStatus === "favorites") {
    return [...items].sort((a, b) =>
      String(b.favorite_saved_at || "").localeCompare(String(a.favorite_saved_at || ""))
    );
  }
  return previousSortItemsV8(items);
};

function favoriteTrackingV8(item) {
  if (!item.is_favorite) return "";
  const availability = item.favorite_is_current
    ? "目前結果仍保留"
    : "目前搜尋結果未出現，保留收藏快照";
  return `<div class="favorite-tracking ${item.favorite_is_current ? "current" : "stale"}">
    <strong>${escapeHtml(availability)}</strong>
    <span>收藏於：${escapeHtml(dateText(item.favorite_saved_at))}</span>
    <span>最近看到：${escapeHtml(dateText(item.favorite_last_seen_at))}</span>
  </div>`;
}

const previousListingCardV8 = listingCard;
listingCard = function listingCardV8(item) {
  let html = previousListingCardV8(item);
  const isFavorite = Boolean(item.is_favorite);
  const button = `<button class="favorite-toggle ${isFavorite ? "active" : ""}" type="button"
    data-source="${escapeHtml(item.source || "591")}" data-listing-id="${escapeHtml(item.id)}"
    data-favorite-action="${isFavorite ? "remove" : "add"}" aria-pressed="${isFavorite}"
    aria-label="${isFavorite ? "取消收藏" : "加入收藏"}">${isFavorite ? "★ 已收藏" : "☆ 收藏"}</button>`;
  html = html.replace('<a class="listing-link"', `${button}<a class="listing-link"`);
  html = html.replace("<h2>", `${favoriteTrackingV8(item)}<h2>`);
  if (isFavorite) html = html.replace("listing-card", "listing-card favorite-card");
  return html;
};

const previousRenderResultsV8 = renderResults;
renderResults = function renderResultsV8() {
  previousRenderResultsV8();
  if (state.activeStatus === "favorites" && !(state.payload?.favorites || []).length) {
    document.querySelector("#results").innerHTML = emptyState(
      "還沒有收藏房源",
      "看到想持續追蹤的房子時，按下卡片內的「☆ 收藏」。"
    );
  }
};

const previousRenderNavigationV8 = renderNavigation;
renderNavigation = function renderNavigationV8() {
  previousRenderNavigationV8();
  const count = state.payload ? (state.payload.favorites || []).length : 0;
  document.querySelector("#tab-favorites").textContent = count;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.status === state.activeStatus);
  });
  const favoriteOption = resultSortV8.querySelector('[value="favorite_saved"]');
  favoriteOption.hidden = state.activeStatus !== "favorites";
  if (state.activeStatus === "favorites") {
    document.querySelector("#active-goal-total").textContent = `${count} 筆過去收藏`;
  }
};

document.querySelector('[data-status="favorites"]').addEventListener("click", (event) => {
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
  event.currentTarget.classList.add("active");
  state.activeStatus = "favorites";
  state.nearFailureFilter = "";
  resultSortV8.querySelector('[value="favorite_saved"]').hidden = false;
  resultSortV8.value = "favorite_saved";
  renderNavigation();
  renderResults();
});

document.querySelectorAll('.tab:not([data-status="favorites"])').forEach((tab) => {
  tab.addEventListener("click", () => {
    const favoriteOption = resultSortV8.querySelector('[value="favorite_saved"]');
    favoriteOption.hidden = true;
    if (resultSortV8.value === "favorite_saved") resultSortV8.value = "metric";
  });
});

document.querySelectorAll(".goal-card").forEach((card) => {
  card.addEventListener("click", () => {
    if (state.activeStatus !== "favorites") return;
    state.activeStatus = "exact_match";
    resultSortV8.value = "metric";
    renderNavigation();
    renderResults();
  });
});

document.querySelector("#results").addEventListener("click", async (event) => {
  const button = event.target.closest("button.favorite-toggle");
  if (!button) return;
  button.disabled = true;
  try {
    const response = await fetch("/api/favorites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: button.dataset.source,
        id: button.dataset.listingId,
        action: button.dataset.favoriteAction,
      }),
    });
    state.payload = await readJsonResponse(response, "收藏操作失敗");
    renderNavigation();
    renderResults();
  } catch (error) {
    document.querySelector("#status-message").textContent = `收藏操作失敗：${error.message}`;
    button.disabled = false;
  }
});

