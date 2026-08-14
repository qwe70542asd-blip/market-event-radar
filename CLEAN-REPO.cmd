@echo off
setlocal
cd /d "%~dp0"

echo [Market Event Radar] Synchronizing repository cleanup with VERSION.json ...
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 scripts\cleanup_repo.py
) else (
  python scripts\cleanup_repo.py
)
if ERRORLEVEL 1 (
  echo Cleanup failed. Do not commit yet.
  exit /b 1
)

echo.
echo Repository cleanup complete. GitHub Desktop should now show both updates and deletions.
endlocal
