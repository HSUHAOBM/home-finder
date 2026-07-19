@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
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
wscript.exe //nologo "%~dp0啟動找房介面_隱藏.vbs" %*
exit /b 0
