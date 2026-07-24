# 舊版 591 公開售屋頁來源（診斷用）

這個模組直接解析搜尋頁伺服器 HTML，只保留作為來源診斷與離線測試。日常找房請使用 `home_finder.web_app_v8`；它會透過瀏覽器讀取目前的動態頁面，並保留收藏紀錄。

本模組不使用未公開 API，也不繞過登入、驗證碼或其他存取控制。

## 使用方式

```powershell
Copy-Item config.live.example.json config.live.json
uv run python -m home_finder.live_cli --config config.live.json
```

離線驗證可使用：

```powershell
uv run python -m home_finder.live_cli --config config.live.example.json --input data/sample_listings.json
```

`region_id` 是 591 搜尋網址上的縣市代碼，例如台北市為 `1`、新北市為 `3`。

## 限制與保護

- 搜尋頁的主要列表由前端動態載入，伺服器 HTML 通常只有少量物件；程式會如實顯示讀取筆數，不把它當成完整搜尋結果。
- 每個頁面快取一小時到 `data/cache/`。
- 一次最多讀取 5 頁；非快取請求至少間隔 2 秒。
- 網站改版或沒有公開房源連結時會直接報錯。
- 使用前應重新確認網站服務條款。價格、坪數、屋況與事故資訊仍須以仲介、屋主及正式文件為準。
