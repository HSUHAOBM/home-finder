const activeGoal = document.querySelector(".active-goal");
if (activeGoal) {
  activeGoal.insertAdjacentHTML("beforeend", `
    <div class="goal-action-bar">
      <button id="selected-settings-button" class="settings-button" type="button">調整此目標條件</button>
      <button id="selected-search-button" class="search-button" type="button">
        <span class="button-dot" aria-hidden="true"></span>
        <span id="selected-search-label">搜尋此目標</span>
      </button>
    </div>`);
}

const tabs = document.querySelector(".tabs");
if (tabs) {
  tabs.querySelector('[data-status="needs_verification"]').insertAdjacentHTML(
    "afterend",
    '<button class="tab near-tab" type="button" data-status="near_match">只差一項 <span id="tab-near">0</span></button>'
  );
  tabs.insertAdjacentHTML(
    "beforebegin",
    '<section id="goal-insight" class="goal-insight" aria-live="polite"></section>'
  );
}

function activeProfileClass(profile) {
  return {
    "大樓公寓華廈": "condo-settings",
    "透天別墅": "house-settings",
    "預售屋": "presale-settings",
  }[profile];
}

function openActiveSettings() {
  fillSettingsForm();
  const profile = state.activeProfile;
  document.querySelectorAll(".settings-profile").forEach((section) => {
    section.hidden = !section.classList.contains(activeProfileClass(profile));
  });

  const isPresale = profile === "預售屋";
  document.querySelector("#resale-details").closest("label").hidden = isPresale;
  document.querySelector("#presale-details").closest("label").hidden = !isPresale;
  document.querySelector("#search-pages").closest("label").hidden = isPresale;
  document.querySelector("#publish-days").closest("label").hidden = isPresale;

  const meta = PROFILE_META[profile];
  document.querySelector(".dialog-header h2").textContent = `調整${meta.number}條件`;
  document.querySelector(".dialog-header p").textContent =
    "只顯示目前目標的條件；行政區仍共用。儲存後會立即重算現有結果。";
  document.querySelector("#settings-dialog").showModal();
}

function renderInsight() {
  const box = document.querySelector("#goal-insight");
  if (!box || !state.payload) return;
  const insight = (state.payload.profile_insights || {})[state.activeProfile];
  if (!insight) {
    box.innerHTML = "";
    return;
  }
  const reasons = (insight.top_reasons || [])
    .map((item) => `<li><span>${escapeHtml(item.reason)}</span><b>${item.count} 筆</b></li>`)
    .join("");
  const headline = insight.qualified
    ? `目前有 ${insight.qualified} 筆直接符合`
    : "目前沒有完全符合，但先別把候選全部丟掉";
  const near = insight.near_match
    ? `<button id="show-near-matches" type="button">${insight.near_match} 筆只差一項，直接查看</button>`
    : "<span>目前沒有只差一項的候選</span>";
  box.innerHTML = `
    <div><strong>${headline}</strong><p>${near}</p></div>
    ${reasons ? `<div class="reason-summary"><span>主要排除原因</span><ul>${reasons}</ul></div>` : ""}`;
  const nearButton = document.querySelector("#show-near-matches");
  if (nearButton) {
    nearButton.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelector('[data-status="near_match"]').classList.add("active");
      state.activeStatus = "near_match";
      renderResults();
    });
  }
}

const previousListingCardV5 = listingCard;
listingCard = function listingCardV5(item) {
  if (item.status !== "near_match") return previousListingCardV5(item);
  const html = previousListingCardV5({ ...item, status: "rejected" });
  return html
    .replace("listing-card rejected-card", "listing-card near-card")
    .replace("badge rejected", "badge near_match")
    .replace(">已排除</span>", ">只差一項</span>")
    .replace("<strong>排除原因</strong>", "<strong>目前只差這一項</strong>");
};

const previousGoalRuleV5 = goalRule;
goalRule = function goalRuleV5(profile) {
  let text = previousGoalRuleV5(profile);
  if (profile === "大樓公寓華廈" && state.settings) {
    const config = state.settings.profiles[profile];
    text = text.replace("・樓層 ≥ 2/3", "");
    text += config.require_high_floor ? "・樓層 ≥ 2/3 必要" : "・樓層 ≥ 2/3 優先";
  }
  return text;
};

const previousGoalDescriptionV5 = goalDescription;
goalDescription = function goalDescriptionV5(profile) {
  let text = previousGoalDescriptionV5(profile);
  if (profile !== "大樓公寓華廈" || !state.settings) return text;
  const config = state.settings.profiles[profile];
  if (!config.require_high_floor) {
    text += " 樓層達全棟 2/3（例如 15 樓中的 10 樓以上）會加分，但不會單獨淘汰房源。";
  }
  return text;
};

const previousRenderNavigationV5 = renderNavigation;
renderNavigation = function renderNavigationV5() {
  previousRenderNavigationV5();
  const insight = state.payload && state.payload.profile_insights
    ? state.payload.profile_insights[state.activeProfile]
    : null;
  document.querySelector("#tab-near").textContent = insight ? insight.near_match : 0;
  const meta = PROFILE_META[state.activeProfile];
  document.querySelector("#selected-search-label").textContent = `搜尋${meta.title}`;
  renderInsight();
};

const previousRenderStatusV5 = renderStatus;
renderStatus = function renderStatusV5(status) {
  previousRenderStatusV5(status);
  const button = document.querySelector("#selected-search-button");
  const settingsButton = document.querySelector("#selected-settings-button");
  if (!button || !settingsButton) return;
  button.disabled = status.running;
  settingsButton.disabled = status.running;
  button.classList.toggle("running", status.running);
  const activeMeta = PROFILE_META[state.activeProfile];
  document.querySelector("#selected-search-label").textContent = status.running
    ? `正在搜尋${PROFILE_META[status.active_profile]?.title || "房源"}`
    : `搜尋${activeMeta.title}`;
};

async function startSelectedSearch() {
  const button = document.querySelector("#selected-search-button");
  button.disabled = true;
  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: state.activeProfile }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || payload.message || "無法開始搜尋");
    renderStatus(payload);
  } catch (error) {
    document.querySelector("#status-message").textContent = `無法開始：${error.message}`;
    button.disabled = false;
  }
}

document.querySelector("#selected-settings-button").addEventListener("click", openActiveSettings);
document.querySelector("#selected-search-button").addEventListener("click", startSelectedSearch);
document.querySelector('[data-status="near_match"]').addEventListener("click", (event) => {
  document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
  event.currentTarget.classList.add("active");
  state.activeStatus = "near_match";
  renderResults();
});
