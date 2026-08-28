@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo Market Event Radar v11.4.53 - Full Replace Package
echo 建議先刪除舊檔，再把這包完整覆蓋進專案資料夾
echo ============================================================
echo.
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 scripts\cleanup_repo.py
) else (
  python scripts\cleanup_repo.py
)
echo.
echo 清理完成後，請用 GitHub Desktop 檢查 Changes，再 Commit / Push。
pause
endlocal
