@echo off
setlocal
cd /d "%~dp0"

echo [Market Event Radar] Cleaning accidental nested repository copies under scripts\ ...
for %%D in (.github assets data docs tests scripts edge) do (
  if exist "scripts\%%D" (
    echo Removing scripts\%%D
    rmdir /s /q "scripts\%%D"
  )
)
for %%F in (.gitignore .nojekyll 404.html asset.html data-status.html event.html index.html institutional.html news.html portfolio.html tw-market.html README.md GITHUB-DESKTOP-UPDATE.txt VALIDATION.json VALIDATION.txt VERSION.json manifest.webmanifest service-worker.js requirements.txt CLEAN-REPO.cmd) do (
  if exist "scripts\%%F" (
    echo Removing scripts\%%F
    del /f /q "scripts\%%F"
  )
)
echo Repository nested-copy cleanup complete.
echo You can now review the deletions in GitHub Desktop before committing.
endlocal
