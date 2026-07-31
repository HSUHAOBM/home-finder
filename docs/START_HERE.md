# 高雄找房工具：從這裡開始

## 你的條件已寫入

- 區域：楠梓區、三民區、橋頭區、大社區
- 硬上限：1,200 萬；1,100 萬內優先
- 大樓／公寓／華廈：平面汽車位、主建物至少 15 坪、至少 2 房
- 透天／別墅：詳情型態必須真的是透天或別墅，且有汽車位
- 預售屋：至少 2 房，建案須規劃平面車位；總價、戶別車位與主建物未公開時列待確認
- 加分：高樓或頂樓、2 衛浴、屋齡 30 年內；透天有花園

完整判斷規格請看 [`USER_REQUIREMENTS.md`](USER_REQUIREMENTS.md)。

## 第一次安裝

```powershell
if (-not (Test-Path config.user.json)) {
    Copy-Item config.user.example.json config.user.json
}
uv sync --dev
```

本機須有 Google Chrome。程式會以正常瀏覽器讀取公開頁面，不處理登入或驗證碼。

## 開啟找房介面

直接雙擊專案資料夾裡的 `開啟找房介面.cmd`，或在 PowerShell 執行：

```powershell
uv run python -m home_finder.web_app_v9
```

瀏覽器會開啟 `http://127.0.0.1:8765`，黑色 CMD 視窗則會保持開啟。先選擇購屋目標與搜尋範圍，再開始搜尋；搜尋期間請保持命令視窗開啟。使用完畢後，在 CMD 視窗按 `Ctrl+C`，或直接關閉視窗，即可停止服務。

介面會顯示完全符合、可接受、待確認、差強人意與已排除房源。完整結果保存在 `output/current-results.json`，方便下次開啟與日後比較。

看到想持續追蹤的房源，可按卡片內的「☆ 收藏」；之後從「我的收藏」查看。收藏後若總價、車位、標題、坪數、房數或樓層等資料改變，卡片會列出變更前後內容並保留歷史。收藏資料獨立保存在 `data/favorites.json`，不會因重新搜尋或房源暫時未出現而消失。

若程式更新了評分規則，第一次開啟時會用既有房源在本機重新評估，不會額外連線爬取 591。

## 執行測試

```powershell
uv run pytest
```

## 判斷原則

- 標題寫平車但詳情寫無車位，以詳情為準並淘汰。
- 「室內 15 坪」以主建物為準，不使用含公設、車位的權狀總坪數。
- 預售屋只有銷售坪數時，以公設比估算供參考；估算連附屬建物都低於 15 坪就淘汰，否則仍需向案場索取主建物表。
- 同行政區、社區／地址、坪數、房數與樓層相同者列為疑似重複，即使開價不同。
- 程式限制請求間隔至少 2 秒並使用快取。請自行確認 591 最新服務條款；不要設定高頻排程或嘗試繞過網站限制。

## 調整條件與抓取量

優先使用頁面上的「調整此目標條件」。設定會存入 `config.user.json`：

- `editable_criteria.search.resale_details`：中古屋最多開幾筆詳情。
- `editable_criteria.search.presale_details`：預售屋最多開幾筆詳情。
- `editable_criteria.search.pages`：每日更新要讀取的中古屋頁數。
- `editable_criteria.search.publish_days`：每日更新要搜尋的刊登天數。
- `source.delay_seconds`：請求間隔，不能低於 2 秒。
- `source.headless`：設為 `false` 可看見瀏覽器操作過程。
