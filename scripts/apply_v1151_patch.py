#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json, re, shutil

BUILD_OLD="v11.5.0"
BUILD_NEW="v11.5.1"
QUERY_OLD="11.5.0"
QUERY_NEW="11.5.1"

def die(msg: str, code: int=2):
    print(f"[ERROR] {msg}")
    raise SystemExit(code)

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")

def replace_version_text(text: str) -> str:
    return text.replace(BUILD_OLD, BUILD_NEW).replace(f"?v={QUERY_OLD}", f"?v={QUERY_NEW}")

def patch_html(path: Path):
    text=read_text(path)
    text=text.replace("assets/v11.5.0-overrides.css","assets/v11.5.1-overrides.css")
    text=replace_version_text(text)
    text=re.sub(r'<script(?![^>]*\bdefer\b)(\s+[^>]*\bsrc="[^"]+"[^>]*)>', r'<script defer\1>', text)
    fast='<script defer src="assets/v11.5.1-fast-boot.js?v=11.5.1"></script>'
    if fast not in text:
        pos=text.find("<script ")
        if pos>=0:text=text[:pos]+fast+"\n"+text[pos:]
        else:text=text.replace("</body>",fast+"\n</body>")
    write_text(path,text)

def patch_stale_guard(path: Path):
    text=read_text(path)
    text=text.replace("// v11.5.0:","// v11.5.1:")
    text=text.replace("{force:true}","{force:false}")
    old='const boot=()=>{assess();setTimeout(assess,2000);setInterval(assess,60000);const root=document.getElementById("marketStateSummary");if(root)new MutationObserver(()=>{if(!applying)applyState()}).observe(root,{subtree:true,childList:true,characterData:true,attributes:true})};'
    new='const boot=()=>{const root=document.getElementById("marketStateSummary");if(root)new MutationObserver(()=>{if(!applying)applyState()}).observe(root,{subtree:true,childList:true,characterData:true,attributes:true});const start=()=>assess();if("requestIdleCallback" in window)requestIdleCallback(start,{timeout:1200});else setTimeout(start,350);setTimeout(assess,15000);setInterval(assess,60000)};'
    if old not in text:
        if "setTimeout(assess,15000)" in text and "{force:true}" not in text:
            return
        die("stale-market-guard.js baseline did not match expected v11.5.0 boot block")
    write_text(path,text.replace(old,new))

def patch_shared(path: Path):
    text=read_text(path)
    text=text.replace('APP_VERSION="v11.5.0"','APP_VERSION="v11.5.1"')
    text=text.replace("timeout=6200","timeout=2600")
    lines=[]
    for line in text.splitlines():
        if "for(const legacy of [`mr-data-cache-v11.4.46:" in line:
            continue
        lines.append(line)
    write_text(path,"\n".join(lines)+"\n")

def patch_version_sensitive_text_files(root: Path):
    selected=[]
    for base in (root/"scripts", root/"tests", root/".github"/"workflows"):
        if not base.exists():continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in {".py",".yml",".yaml",".sh"}:
                selected.append(p)
    selected += [p for p in [root/"README.md",root/"GITHUB-DESKTOP-UPDATE.txt"] if p.exists()]
    for p in selected:
        try:text=read_text(p)
        except UnicodeDecodeError:continue
        new=replace_version_text(text).replace("verify-v11-5-0","verify-v11-5-1")
        if new!=text:write_text(p,new)

def main():
    root=Path(__file__).resolve().parents[1]
    required=[root/"VERSION.json",root/"index.html",root/"assets"/"shared.js",root/"assets"/"stale-market-guard.js",root/"service-worker.js"]
    missing=[str(p.relative_to(root)) for p in required if not p.exists()]
    if missing:die("請把整個更新 ZIP 解壓到 market-event-radar 專案根目錄後再執行。缺少："+", ".join(missing))

    version=json.loads(read_text(root/"VERSION.json"))
    current=str(version.get("version",""))
    if current not in {BUILD_OLD,BUILD_NEW}:die(f"此更新包只接受 {BUILD_OLD} / {BUILD_NEW}，目前是 {current or 'unknown'}")

    patch_html_files=list(root.glob("*.html"))
    for page in patch_html_files:patch_html(page)
    patch_stale_guard(root/"assets"/"stale-market-guard.js")
    patch_shared(root/"assets"/"shared.js")

    old_css=root/"assets"/"v11.5.0-overrides.css"
    new_css=root/"assets"/"v11.5.1-overrides.css"
    if old_css.exists() and not new_css.exists():shutil.copy2(old_css,new_css)
    if not new_css.exists():die("缺少 overrides CSS，無法建立 v11.5.1 樣式檔")

    for rel in ["assets/runtime-config.js","assets/home.js","assets/pwa-install.js","assets/date-alerts.js"]:
        p=root/rel
        if p.exists():
            text=read_text(p); new=replace_version_text(text)
            if new!=text:write_text(p,new)

    manifest=root/"manifest.webmanifest"
    if manifest.exists():
        text=read_text(manifest).replace("market-event-radar-v11.5.0","market-event-radar-v11.5.1")
        write_text(manifest,text)

    version.update({
        "version": BUILD_NEW,
        "name": "fast-boot-runtime-stability-release",
        "schema_version": "11.5",
    })
    write_text(root/"VERSION.json",json.dumps(version,ensure_ascii=False,indent=2)+"\n")

    patch_version_sensitive_text_files(root)

    validation=read_text(root/"VALIDATION-v11.5.1.txt")
    write_text(root/"VALIDATION.txt",validation)
    validation_json={
        "version":BUILD_NEW,
        "status":"patch-self-validated; hosted-release-gates-required-after-push",
        "performance_hotfix":{
            "deferred_external_scripts":True,
            "startup_fetch_dedupe":True,
            "external_branch_fail_fast_ms":{"raw":2800,"cdn":2200},
            "stale_guard_force_reload_removed":True,
            "service_worker_reload_loop_removed":True,
            "service_worker_install_precache_reduced":True,
            "legacy_v11_4_cache_promotion_removed":True
        }
    }
    write_text(root/"VALIDATION.json",json.dumps(validation_json,ensure_ascii=False,indent=2)+"\n")

    for old in [root/"VALIDATION-v11.5.0.txt",root/"assets"/"v11.5.0-overrides.css",root/"ONE-CLICK-REPLACE-v11.5.0.cmd"]:
        if old.exists():old.unlink()

    print("[PASS] v11.5.1 integrated performance update applied.")
    print("[INFO] 修正：defer 平行載入、fetch 去重/快速回退、stale guard 不重抓、SW 不強制 reload。")
    print("[NEXT] GitHub Desktop 檢查變更後 commit/push；Hosted Verify 必須跑綠。")

if __name__=="__main__":
    main()
