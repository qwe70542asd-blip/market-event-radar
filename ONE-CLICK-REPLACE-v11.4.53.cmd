@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo Market Event Radar v11.4.53 - One Click Replace
echo 會覆蓋新版檔案並刪除舊版本殘留，不會刪除 .git
echo ============================================================
echo.
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 apply_v11_4_53.py
) else (
  python apply_v11_4_53.py
)
if ERRORLEVEL 1 (
  echo.
  echo [FAILED] 更新失敗，請不要 Commit。
  pause
  exit /b 1
)
echo.
echo [DONE] v11.4.53 已完成覆蓋與舊檔清理。
echo 請打開 GitHub Desktop 檢查 Changes，再 Commit / Push。
pause
endlocal
