@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo Market Event Radar v11.4.54 - Full Replace Package
echo 完整覆蓋後執行本檔，可清除舊版本殘留；不會刪除 .git
echo ============================================================
where py >nul 2>nul
if %ERRORLEVEL%==0 (py -3 scripts\cleanup_repo.py) else (python scripts\cleanup_repo.py)
if ERRORLEVEL 1 (echo [FAILED] 清理失敗，請不要 Commit。& pause & exit /b 1)
echo [DONE] 請用 GitHub Desktop 檢查 Changes，再 Commit / Push。
pause
endlocal
