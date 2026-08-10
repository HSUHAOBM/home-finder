const MORTGAGE_DEFAULT_RATE_V11 = 2.30;
const MORTGAGE_SCENARIOS_V11 = [
  { downPaymentRate: 20, years: 30 },
  { downPaymentRate: 20, years: 40 },
  { downPaymentRate: 30, years: 30 },
  { downPaymentRate: 30, years: 40 },
];

const mortgageHeaderButtonV11 = document.createElement("button");
mortgageHeaderButtonV11.id = "mortgage-calculator-button";
mortgageHeaderButtonV11.className = "settings-button mortgage-header-button";
mortgageHeaderButtonV11.type = "button";
mortgageHeaderButtonV11.textContent = "房貸試算";
document.querySelector(".goal-action-bar").prepend(mortgageHeaderButtonV11);

const mortgageDialogV11 = document.createElement("dialog");
mortgageDialogV11.id = "mortgage-dialog";
mortgageDialogV11.className = "mortgage-dialog";
mortgageDialogV11.innerHTML = `
  <div class="mortgage-dialog-body">
    <div class="dialog-header mortgage-dialog-header">
      <div>
        <span class="section-label">MORTGAGE CALCULATOR</span>
        <h2>房貸試算</h2>
        <p>以本息平均攤還，比較不同頭期款與貸款年限。</p>
      </div>
      <button id="mortgage-close" class="icon-button" type="button" aria-label="關閉房貸試算">×</button>
    </div>
    <div class="mortgage-inputs">
      <label>房屋總價（萬）
        <input id="mortgage-price" type="number" min="1" step="1" inputmode="decimal" placeholder="例如 1,000">
      </label>
      <label>年利率（%）
        <input id="mortgage-rate" type="number" min="0" max="20" step="0.01" inputmode="decimal" value="2.30">
      </label>
    </div>
    <div class="mortgage-rate-reference">
      <strong>市場參考利率：2.30%</strong>
      <span>央行 2026 年 6 月五大銀行新承做購屋貸款平均利率約 2.299%。</span>
      <a href="https://www.cbc.gov.tw/tw/cp-302-192614-192cb-1.html" target="_blank" rel="noopener noreferrer">查看中央銀行統計</a>
    </div>
    <p id="mortgage-error" class="mortgage-error" role="alert"></p>
    <div id="mortgage-results" class="mortgage-results" aria-live="polite"></div>
    <div class="mortgage-notes">
      <strong>試算前提</strong>
      <p>假設整段期間利率不變；40 年通常月付較低，但總利息高於 30 年。實際利率及成數仍依信用、收入、職業、房屋鑑價與銀行核貸為準。</p>
      <p>不含契稅、代書費、仲介費、保險、裝修與銀行開辦費。第一版不計算本金平均攤還、到期還本、寬限期及提前還款。</p>
    </div>
  </div>
`;
document.body.append(mortgageDialogV11);
document.querySelector("#mortgage-rate").value = MORTGAGE_DEFAULT_RATE_V11.toFixed(2);

function calculateMortgageV11(principal, annualRate, years) {
  const months = years * 12;
  if (annualRate === 0) {
    const monthlyPayment = principal / months;
    return { monthlyPayment, totalInterest: 0, totalPayment: principal };
  }
  const monthlyRate = annualRate / 100 / 12;
  const factor = Math.pow(1 + monthlyRate, months);
  const monthlyPayment = principal * monthlyRate * factor / (factor - 1);
  const totalPayment = monthlyPayment * months;
  return {
    monthlyPayment,
    totalInterest: totalPayment - principal,
    totalPayment,
  };
}

function mortgageYuanV11(value) {
  return `NT$ ${Math.round(value).toLocaleString("zh-TW")}`;
}

function mortgageWanV11(value) {
  return `${(value / 10000).toLocaleString("zh-TW", { maximumFractionDigits: 1 })} 萬`;
}

function mortgageScenarioCardV11(priceYuan, annualRate, scenario) {
  const downPayment = priceYuan * scenario.downPaymentRate / 100;
  const principal = priceYuan - downPayment;
  const result = calculateMortgageV11(principal, annualRate, scenario.years);
  const key = `${scenario.downPaymentRate}-${scenario.years}`;
  return `
    <article class="mortgage-result-card" data-mortgage-scenario="${key}">
      <div class="mortgage-result-heading">
        <span>頭期 ${scenario.downPaymentRate}%</span>
        <strong>貸款 ${scenario.years} 年</strong>
      </div>
      <div class="mortgage-monthly">
        <small>每月固定還款</small>
        <strong data-mortgage-value="monthly">${mortgageYuanV11(result.monthlyPayment)}</strong>
      </div>
      <dl>
        <div><dt>頭期款</dt><dd data-mortgage-value="down">${mortgageWanV11(downPayment)}</dd></div>
        <div><dt>貸款本金</dt><dd data-mortgage-value="principal">${mortgageWanV11(principal)}</dd></div>
        <div><dt>總利息</dt><dd data-mortgage-value="interest">${mortgageWanV11(result.totalInterest)}</dd></div>
        <div><dt>本息總支出</dt><dd data-mortgage-value="total">${mortgageWanV11(result.totalPayment)}</dd></div>
      </dl>
    </article>`;
}

function renderMortgageV11() {
  const priceText = document.querySelector("#mortgage-price").value.trim();
  const rateText = document.querySelector("#mortgage-rate").value.trim();
  const priceWan = Number(priceText);
  const annualRate = Number(rateText);
  const error = document.querySelector("#mortgage-error");
  const results = document.querySelector("#mortgage-results");
  if (!priceText || !Number.isFinite(priceWan) || priceWan <= 0) {
    error.textContent = "請輸入大於 0 的房屋總價。";
    results.innerHTML = "";
    return;
  }
  if (!rateText || !Number.isFinite(annualRate) || annualRate < 0 || annualRate > 20) {
    error.textContent = "年利率請輸入 0%～20%。";
    results.innerHTML = "";
    return;
  }
  error.textContent = "";
  const priceYuan = priceWan * 10000;
  results.innerHTML = MORTGAGE_SCENARIOS_V11
    .map((scenario) => mortgageScenarioCardV11(priceYuan, annualRate, scenario))
    .join("");
}

function openMortgageV11(price = null) {
  const priceInput = document.querySelector("#mortgage-price");
  if (Number.isFinite(Number(price)) && Number(price) > 0) {
    priceInput.value = Number(price);
  }
  renderMortgageV11();
  mortgageDialogV11.showModal();
  priceInput.focus();
}

const previousListingCardV11 = listingCard;
listingCard = function listingCardV11(item) {
  let html = previousListingCardV11(item);
  const price = Number(item.price);
  const available = Number.isFinite(price) && price > 0;
  const button = `<button class="mortgage-card-button" type="button"
    ${available ? `data-mortgage-price="${price}"` : "disabled"}
    title="${available ? "帶入這筆房源總價" : "總價待確認，無法試算"}">
    房貸試算
  </button>`;
  html = html.replace('<button class="favorite-toggle', `${button}<button class="favorite-toggle`);
  return html;
};

mortgageHeaderButtonV11.addEventListener("click", () => openMortgageV11());
document.querySelector("#mortgage-close").addEventListener("click", () => mortgageDialogV11.close());
document.querySelector("#mortgage-price").addEventListener("input", renderMortgageV11);
document.querySelector("#mortgage-rate").addEventListener("input", renderMortgageV11);
document.addEventListener("click", (event) => {
  const button = event.target.closest(".mortgage-card-button[data-mortgage-price]");
  if (button) openMortgageV11(button.dataset.mortgagePrice);
});
mortgageDialogV11.addEventListener("click", (event) => {
  if (event.target === mortgageDialogV11) mortgageDialogV11.close();
});

window.calculateMortgageV11 = calculateMortgageV11;
