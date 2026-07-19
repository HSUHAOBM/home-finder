@echo off
chcp 65001 >nul
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo 找不到 uv，請先安裝 uv 後再試。
  pause
  exit /b 1
)
uv run python -m home_finder.web_app_v7 %*
if errorlevel 1 (
  echo.
  echo 找房介面未正常啟動，請保留此畫面以便檢查。
  pause
)
