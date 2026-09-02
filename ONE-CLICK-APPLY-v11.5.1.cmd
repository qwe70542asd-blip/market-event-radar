@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 scripts\apply_v1151_patch.py
) else (
  python scripts\apply_v1151_patch.py
)
if errorlevel 1 (
  echo.
  echo [FAILED] v11.5.1 update was not applied.
  pause
  exit /b 1
)
echo.
echo [DONE] v11.5.1 update applied. Open GitHub Desktop and review the changes.
pause
