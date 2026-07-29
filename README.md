# 我的高雄找房雷達

本機執行的高雄房源搜尋與追蹤工具。它透過瀏覽器低頻讀取 591 與永慶公開頁面，將房源整理成三種購屋目標，再依必要條件、理想條件與資料完整度分類。

目前正式入口是 `home_finder.web_app_v9`，主要功能包括：

- 大樓／公寓／華廈、透天／車墅、預售屋分開評估。
- 完全符合、可接受、待確認、差強人意、已排除等可稽核分類。
- 超過 5 個行政區時自動分批搜尋，避免 591 的選區上限。
- 591 與永慶中古屋合併搜尋，跨網站疑似同一物件群組顯示並保留各來源連結。
- 保留成功爬蟲時間、首次發現時間與搜尋／條件歷史。
- 收藏房源並長期保留快照，即使房源暫時未出現在最新結果中仍可追蹤。

## 快速開始

### 1. 準備環境

需要 Windows、[uv](https://docs.astral.sh/uv/) 與 Google Chrome。在專案根目錄執行：

```powershell
uv sync --dev
```

首次使用且尚未有個人設定時：

```powershell
Copy-Item config.user.example.json config.user.json
```

`config.user.json` 是本機個人設定，不會納入 Git。

### 2. 開啟介面

直接雙擊根目錄的：

```text
開啟找房介面.cmd
```

也可以從 PowerShell 啟動：

```powershell
uv run python -m home_finder.web_app_v9
```

瀏覽器預設開啟 <http://127.0.0.1:8765>。CMD 視窗必須保持開啟；要停止服務時，在視窗按 `Ctrl+C` 或直接關閉視窗。

啟動器已使用 `--reload`，一般程式或頁面調整後會自動重載，不需要反覆關閉重開。

## 使用流程

1. 選擇購屋目標。
2. 選擇「每日更新」或「完整盤點」。
3. 視需要調整行政區、價格、坪數、房數、車位、屋齡與樓層條件。
4. 開始搜尋，等待畫面顯示完成。
5. 從分類頁籤檢查結果與每一項不符合原因。
6. 對想持續追蹤的房源按「☆ 收藏」，之後從「我的收藏」查看。

房價、坪數、車位、屋況及廣告描述仍須向仲介、屋主與正式文件確認。

## 目錄結構

| 路徑 | 用途 |
| --- | --- |
| `開啟找房介面.cmd` | Windows 正式啟動入口 |
| `config.user.example.json` | 個人搜尋條件範例 |
| `src/home_finder/` | 爬蟲、評分、Flask API 與前端程式 |
| `tests/` | 單元、整合與瀏覽器測試 |
| `docs/` | 操作說明、購屋規格、來源限制與舊流程文件 |
| `examples/` | 舊 CLI 設定與離線房源範例 |
| `data/` | 收藏、歷史、診斷與快取等本機資料 |
| `output/` | 目前搜尋結果與摘要 |

## 本機資料

以下資料不會納入 Git：

| 路徑 | 內容 |
| --- | --- |
| `config.user.json` | 目前使用中的個人條件 |
| `data/favorites.json` | 收藏房源與收藏時間 |
| `data/listing_history.json` | 首次發現、再次出現與可能下架紀錄 |
| `data/search_history.json` | 成功完成的搜尋紀錄 |
| `data/settings_history.json` | 可重新載入的條件版本 |
| `data/cache/` | 各房源網站的詳情快取 |
| `output/current-results.json` | 目前完整搜尋結果 |

## 開發與測試

執行一般測試：

```powershell
uv run pytest
```

執行真實瀏覽器 E2E：

```powershell
$env:RUN_BROWSER_E2E = "1"
uv run pytest -q tests/test_browser_e2e.py
```

執行樂屋網六區平衡獨立試爬（每區第一頁；預設把 Chrome 移到螢幕外背景執行，不會混入正式結果）：

```powershell
uv run python -m home_finder.rakuya_pilot --details 15
```

結果、各行政區取樣數、保守重複率與優先候選的詳情驗證會寫入 `output/rakuya-pilot.json`。程式只替數字條件先過關的不同房屋讀取詳情；候選會跨行政區輪流挑選，車位判定以詳情欄位為準。
若要看著瀏覽器執行，可在命令後加上 `--show-browser`。背景模式仍使用正常 Chrome 以通過網站檢查，工作列圖示可能短暫出現。
若樂屋狀態失效，程式會保留原報告並回報安全驗證，不會記成 0 筆；需要人工驗證時再使用 `--show-browser`。舊的多行政區合併取樣只保留作診斷，可加 `--combined-districts --pages 3`。


離線舊版 CLI 範例：

```powershell
uv run python -m home_finder.cli --config examples/config.example.json --input examples/sample_listings.json
```

## 文件索引

- [完整操作說明](docs/START_HERE.md)
- [網頁介面說明](docs/WEB_UI.md)
- [個人購屋篩選規格](docs/USER_REQUIREMENTS.md)
- [房源來源限制與分批規則](docs/SOURCE_LIMITS.md)
- [舊版公開 HTML 來源診斷](docs/LIVE_USAGE.md)

## 使用限制

本工具只低頻讀取公開頁面，不處理登入、驗證碼或其他存取控制。外部網站結構、服務規範與跨站轉刊方式可能變動；新增來源或調整爬蟲前，請先更新[來源限制文件](docs/SOURCE_LIMITS.md)。