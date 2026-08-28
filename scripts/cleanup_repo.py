#!/usr/bin/env python3
"""Keep the repository layout aligned with the current release."""
from __future__ import annotations
import argparse,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SCRIPTS=ROOT/"scripts";VERSION_INFO=json.loads((ROOT/"VERSION.json").read_text(encoding="utf-8"));VERSION=str(VERSION_INFO["version"])
NESTED_DIRS=[".github","assets","data","docs","tests","scripts","edge"]
MIRRORED_FILES=[".gitignore",".nojekyll","404.html","asset.html","data-status.html","event.html","index.html","institutional.html","news.html","portfolio.html","tw-market.html","README.md","GITHUB-DESKTOP-UPDATE.txt","VALIDATION.json","VALIDATION.txt","VERSION.json","manifest.webmanifest","service-worker.js","requirements.txt","requirements-dev.txt","CLEAN-REPO.cmd"]
REDUNDANT_WORKFLOWS=["update-company-disclosures.yml","update-global-market.yml","update-news-asia-risk.yml","update-news-cna.yml","update-news-cnyes.yml","update-news-ctee.yml","update-news-ltn.yml","update-news-moneydj.yml","update-news-technews.yml","update-news-udn.yml","update-news-wealth.yml","update-news-yahoo.yml","update-official-notices.yml","update-stock-news.yml","update-tw-market.yml"]
def version_obsolete_paths():
 found=[];found.extend((ROOT/"tests").glob("test_v*_*.py"));found.extend(SCRIPTS.glob("verify_v*_live_sources.py"));found.extend(ROOT.glob("apply_v*.py"));keep={f"DELETION-MANIFEST-{VERSION}.txt",f"VALIDATION-{VERSION}.txt"}
 for pattern in ("DELETION-MANIFEST-v*.txt","VALIDATION-v*.txt"):
  for path in ROOT.glob(pattern):
   if path.name not in keep:found.append(path)
 current_override=f"{VERSION}-overrides.css"
 for path in (ROOT/"assets").glob("v*-overrides.css"):
  if path.name!=current_override:found.append(path)
 found.extend((ROOT/".github"/"workflows"/name) for name in REDUNDANT_WORKFLOWS);return found
def offenders():
 values=[SCRIPTS/name for name in NESTED_DIRS+MIRRORED_FILES];values.extend(version_obsolete_paths());unique=[];seen=set()
 for path in values:
  if path.exists() and path not in seen:seen.add(path);unique.append(path)
 return sorted(unique,key=lambda p:str(p.relative_to(ROOT)).lower())
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--check",action="store_true");args=parser.parse_args();found=offenders()
 if not found:print(f"repository layout clean for {VERSION}");return 0
 if args.check:
  print(f"stale/conflicting repository files detected for {VERSION}:");[print(" -",p.relative_to(ROOT)) for p in found];return 2
 for path in found:
  shutil.rmtree(path) if path.is_dir() else path.unlink();print("removed",path.relative_to(ROOT))
 print(f"repository cleanup complete for {VERSION}");return 0
if __name__=="__main__":raise SystemExit(main())
