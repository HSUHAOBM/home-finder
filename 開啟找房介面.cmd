@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 高雄找房介面
if not exist ".venv\Scripts\python.exe" (
  where uv >nul 2>nul
  if errorlevel 1 (
    echo 找不到 uv，請先安裝 uv。
    pause
    exit /b 1
  )
  uv sync
  if errorlevel 1 (
    echo.
    echo 建立執行環境失敗，請把這個視窗的錯誤訊息告訴我。
    pause
    exit /b 1
  )
)
echo 正在啟動找房介面，請勿關閉這個視窗。
echo 程式或網頁檔案修改後，服務會自動重載；切回瀏覽器時會自動刷新。
echo 要停止服務時，請在這裡按 Ctrl+C，或直接關閉視窗。
echo.
".venv\Scripts\python.exe" -m home_finder.web_app_v17 --reload %*
set "HOME_FINDER_EXIT_CODE=%ERRORLEVEL%"
echo.
echo 找房介面服務已停止。
if not "%HOME_FINDER_EXIT_CODE%"=="0" (
  echo 程式結束代碼：%HOME_FINDER_EXIT_CODE%
  pause
)
exit /b %HOME_FINDER_EXIT_CODE%
