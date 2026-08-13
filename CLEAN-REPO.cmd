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
for %%F in (apply_v11_4_36.py DELETION-MANIFEST-v11.4.33.txt DELETION-MANIFEST-v11.4.34.txt DELETION-MANIFEST-v11.4.35.txt DELETION-MANIFEST-v11.4.36.txt DELETION-MANIFEST-v11.4.37.txt DELETION-MANIFEST-v11.4.38.txt DELETION-MANIFEST-v11.4.39.txt DELETION-MANIFEST-v11.4.40.txt DELETION-MANIFEST-v11.4.41.txt DELETION-MANIFEST-v11.4.42.txt scripts\verify_v11_4_36_live_sources.py scripts\verify_v11_4_37_live_sources.py scripts\verify_v11_4_38_live_sources.py scripts\verify_v11_4_39_live_sources.py scripts\verify_v11_4_40_live_sources.py scripts\verify_v11_4_41_live_sources.py scripts\verify_v11_4_42_live_sources.py tests\test_v11_4_36_contracts.py tests\test_v11_4_37_contracts.py tests\test_v11_4_37_core.py tests\test_v11_4_38_contracts.py tests\test_v11_4_38_core.py tests\test_v11_4_39_contracts.py tests\test_v11_4_39_core.py tests\test_v11_4_40_contracts.py tests\test_v11_4_40_core.py tests\test_v11_4_41_contracts.py tests\test_v11_4_41_core.py tests\test_v11_4_42_contracts.py tests\test_v11_4_42_core.py docs\V11.4.41-tpex-live-diagnostic.md docs\V11.4.41-release-audit.md docs\V11.4.41.md docs\V11.4.42-tpex-live-diagnostic.md docs\V11.4.42-release-audit.md docs\V11.4.42.md) do (
  if exist "%%F" (
    echo Removing obsolete release file %%F
    del /f /q "%%F"
  )
)

echo Repository nested-copy and obsolete-release cleanup complete.
echo You can now review the deletions in GitHub Desktop before committing.
endlocal
