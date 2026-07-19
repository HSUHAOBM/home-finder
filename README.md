# 我的高雄找房雷達

這是一套在本機執行的個人找房工具。它會讀取 591 公開房源頁面，將中古屋、透天／車墅與預售屋分開整理，再依 `USER_REQUIREMENTS.md` 的必要條件、偏好與待確認項目分類。

目前主要使用方式是網頁介面；命令列工具保留作為離線範例與診斷用途。

## 第一次安裝

需要先安裝 [uv](https://docs.astral.sh/uv/) 與 Google Chrome，然後在專案資料夾執行：

```powershell
if (-not (Test-Path config.user.json)) {
    Copy-Item config.user.example.json config.user.json
}
uv sync --dev
```

## 開啟找房介面

最簡單的方式是雙擊：

```text
開啟找房介面.cmd
```

也可以在 PowerShell 執行：

```powershell
uv run python -m home_finder.web_app_v7
```

介面預設位於 `http://127.0.0.1:8765`。搜尋期間請保持命令視窗開啟；結果會保存在本機，下一次開啟時可繼續查看。

更完整的操作方式請看 `START_HERE.md` 與 `WEB_UI.md`。

## 三種購屋目標

- 大樓／公寓／華廈：總價、主建物坪數、房數與平面車位為必要條件。
- 透天／車墅：確認實際建物型態與汽車停放條件。
- 預售屋：缺少主建物、戶別價格或車位資料時保留為待確認，不直接判定合格。

個人條件集中在 `config.user.json`，並可從網頁介面調整。這個檔案包含個人偏好，不會納入 Git。

## 資料保存

- `output/current-results.json`：目前完整結果，含資料格式與評分規則版本。
- `output/current-summary.md`：命令列流程產生的摘要。
- `data/listing_history.json`：首次發現、再次出現與可能下架紀錄。
- `data/cache/`：降低重複請求的詳情快取。

以上都是本機執行資料，不會納入 Git。範例資料則保留在 `data/sample_listings.json` 與 `data/user_sample_listings.json`。

評分規則版本更新後，介面會用既有房源在本機重新評估一次，不會因此重新爬取 591。

## 測試

```powershell
uv run pytest
```

測試涵蓋條件驗證、評分、重複房源、591 解析、歷史紀錄與網頁 API。

真實瀏覽器 E2E 預設跳過，需明確啟用：

```powershell
$env:RUN_BROWSER_E2E = "1"
uv run pytest -q tests/test_browser_e2e.py
```

若本機尚未安裝 Chromium，先執行 `uv run playwright install chromium`。E2E 使用隔離測試資料，不會改寫個人條件、現有房源或連線爬取 591。

## 專案結構

- `src/home_finder/web_app_v7.py`：目前正式網頁入口。
- `src/home_finder/crawler_591_*.py`：591 搜尋與詳情頁讀取。
- `src/home_finder/user_ranking_v6.py`：目前使用的房源評估入口。
- `src/home_finder/listing_history.py`：房源生命週期紀錄。
- `src/home_finder/templates/`、`static/`：網頁畫面。
- `tests/`：自動化測試。

## 使用限制

工具只讀取公開頁面，不處理登入、驗證碼或其他存取控制；請求間隔不得低於 2 秒。網站內容與服務規範可能變動，使用前應自行確認最新規定。房價、坪數、車位、屋況與事故資訊仍須向仲介、屋主及正式文件再次核對。
