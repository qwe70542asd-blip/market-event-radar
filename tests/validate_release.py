#!/usr/bin/env python3
from pathlib import Path
import json,re,shutil,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
started=time.monotonic();results={};details=[]

def run(name,cmd,timeout=300):
    st=time.monotonic();r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
    elapsed=time.monotonic()-st
    results[name]={'ok':r.returncode==0,'seconds':round(elapsed,3)}
    if r.returncode: details.append(f'{name}:\n{r.stdout}\n{r.stderr}')
    return r

# JSON
st=time.monotonic();ok=True
for p in ROOT.rglob('*.json'):
    try:json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:ok=False;details.append(f'JSON {p.relative_to(ROOT)}: {e}')
results['JSON']={'ok':ok,'seconds':round(time.monotonic()-st,3)}
# Python compile
run('Python compile',[sys.executable,'-m','compileall','-q','scripts','tests'])
# JS
node=shutil.which('node');bad=[];st=time.monotonic()
if node:
    for p in [*sorted((ROOT/'assets').glob('*.js')),ROOT/'service-worker.js']:
        r=subprocess.run([node,'--check',str(p)],capture_output=True,text=True)
        if r.returncode:bad.append(f'{p.name}: {r.stderr}')
results['JavaScript syntax']={'ok':not bad,'seconds':round(time.monotonic()-st,3)};details.extend(bad)
# shell
bad=[];st=time.monotonic()
for p in (ROOT/'scripts').glob('*.sh'):
    r=subprocess.run(['bash','-n',str(p)],capture_output=True,text=True)
    if r.returncode:bad.append(f'{p.name}: {r.stderr}')
results['Shell syntax']={'ok':not bad,'seconds':round(time.monotonic()-st,3)};details.extend(bad)
# YAML
import yaml
bad=[];st=time.monotonic()
for p in (ROOT/'.github/workflows').glob('*.yml'):
    try:
        payload=yaml.safe_load(p.read_text(encoding='utf-8'))
        text=p.read_text(encoding='utf-8')
        values=[int(v) for v in re.findall(r'timeout-minutes:\s*(\d+)',text)]
        if not values or any(v>14 for v in values):raise ValueError(f'timeout values {values}')
    except Exception as e:bad.append(f'{p.name}: {e}')
results['Workflow YAML and <15m ceiling']={'ok':not bad,'seconds':round(time.monotonic()-st,3)};details.extend(bad)
# HTML refs
bad=[];st=time.monotonic()
for p in ROOT.glob('*.html'):
    text=p.read_text(encoding='utf-8')
    for ref in re.findall(r'(?:src|href)="([^"#?]+)',text):
        if ref.startswith(('http://','https://','mailto:','tel:')):continue
        if not (ROOT/ref).exists():bad.append(f'{p.name}: {ref}')
results['HTML references']={'ok':not bad,'seconds':round(time.monotonic()-st,3)};details.extend(bad)
# version/no audio
st=time.monotonic();bad=[]
for p in ROOT.rglob('*'):
    if p.is_file():
        if p.suffix.lower() in {'.m4a','.mp3','.wav'}:bad.append(f'audio: {p.relative_to(ROOT)}')
        if p.suffix.lower() in {'.html','.js','.css','.py','.md','.txt','.json','.yml','.yaml','.webmanifest','.sh'}:
            try:t=p.read_text(encoding='utf-8')
            except:continue
            old_a='11.2.'+'2'; old_b='v11-2-'+'2'
            if old_a in t or old_b in t:bad.append(f'old version: {p.relative_to(ROOT)}')
results['Version and no audio']={'ok':not bad,'seconds':round(time.monotonic()-st,3)};details.extend(bad)
run('Unit tests',[sys.executable,'-m','unittest','discover','-s','tests'],timeout=120)
run('Workflow parser smoke',[sys.executable,'tests/workflow_smoke.py'],timeout=60)
run('Browser E2E',[sys.executable,'tests/e2e_smoke.py'],timeout=120)
results['total_seconds']=round(time.monotonic()-started,3)
all_ok=all(row.get('ok',True) for row in results.values() if isinstance(row,dict)) and results['total_seconds']<900
output={'status':'PASS' if all_ok else 'FAIL','results':results,'details':details}
print(json.dumps(output,ensure_ascii=False,indent=2))
(ROOT/'VALIDATION.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
raise SystemExit(0 if all_ok else 1)
