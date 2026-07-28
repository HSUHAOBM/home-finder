const previousListingCardV9 = listingCard;
listingCard = function listingCardV9(item) {
  let html = previousListingCardV9(item);
  const source = item.source || "未知來源";
  const origin = item.origin_source && item.origin_source !== source
    ? `・原始刊登 ${item.origin_source}`
    : "";
  html = html.replace(
    '<span class="score">',
    `<span class="listing-source">${escapeHtml(source + origin)}</span><span class="score">`
  );
  html = html.replace("591 編號", "來源編號");
  html = html.replace("開啟原始 591 房源", `開啟 ${escapeHtml(source)} 房源`);
  return html;
};

variantsHtmlV6 = function variantsHtmlV9(item) {
  if (!item.variants || item.variants.length <= 1) return "";
  const links = item.variants
    .map((variant) => {
      const source = variant.source || "未知來源";
      const price = variant.price ? number(variant.price) + " 萬" : "價格待確認";
      return `<a href="${safeUrl(variant.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source)}・${escapeHtml(price)}</a>`;
    })
    .join("");
  return `<div class="variant-box"><strong>已將 ${item.variants.length} 筆高度相似刊登合併為同一組</strong><div>${links}</div></div>`;
};
