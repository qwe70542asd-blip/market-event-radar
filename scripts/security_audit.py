#!/usr/bin/env python3
"""Fail-closed security regression audit for v11.4.46."""
from __future__ import annotations
import re,sys
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
FAIL=[]
def bad(msg): FAIL.append(msg)

def text(path): return (ROOT/path).read_text(encoding='utf-8')

# GitHub Actions: no mutable action tags and no high-risk triggers.
# Authorization is allowlisted: only repository contents read/write is permitted;
# no workflow may silently acquire id-token, packages, actions, deployments, issues, etc.
use_re=re.compile(r'(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)')
for path in (ROOT/'.github/workflows').glob('*.yml'):
    body=path.read_text(encoding='utf-8')
    try:
        parsed=yaml.safe_load(body) or {}
        top_permissions=parsed.get('permissions') or {}
        if not isinstance(top_permissions,dict) or set(top_permissions)-{'contents'}:
            bad(f'{path.name}: unexpected top-level permissions: {top_permissions}')
        if top_permissions.get('contents') not in {'read','write'}:
            bad(f'{path.name}: contents permission must be explicit read/write: {top_permissions}')
        for job_name,job in (parsed.get('jobs') or {}).items():
            if not isinstance(job,dict) or 'permissions' not in job: continue
            perms=job.get('permissions') or {}
            if not isinstance(perms,dict) or set(perms)-{'contents'}:
                bad(f'{path.name}/{job_name}: unexpected job permissions: {perms}')
            if perms.get('contents') not in {'read','write'}:
                bad(f'{path.name}/{job_name}: contents permission must be explicit read/write: {perms}')
    except Exception as exc: bad(f'{path.name}: invalid YAML: {exc}'); continue
    if re.search(r'(?m)^\s*(pull_request_target|repository_dispatch)\s*:',body): bad(f'{path.name}: risky trigger enabled')
    for use in use_re.findall(body):
        if use.startswith('./'): continue
        if '@' not in use or not re.fullmatch(r'[^@\s]+@[0-9a-fA-F]{40}',use): bad(f'{path.name}: action not pinned to full SHA: {use}')


# Repository-write token is exposed only to explicit live-branch publication steps.
for path in (ROOT/'.github/workflows').glob('*.yml'):
    parsed=yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    for job_name,job in (parsed.get('jobs') or {}).items():
        for index,step in enumerate(job.get('steps') or []):
            if not isinstance(step,dict): continue
            env=step.get('env') or {}
            if 'GH_TOKEN' in env and 'publish_data_branch.sh' not in str(step.get('run') or ''):
                bad(f'{path.name}/{job_name}/step{index}: GH_TOKEN exposed outside publication step')

checkout_count=0
persist_count=0
for path in (ROOT/'.github/workflows').glob('*.yml'):
    body=path.read_text(encoding='utf-8')
    checkout_count+=body.count('uses: actions/checkout@')
    persist_count+=body.count('persist-credentials: false')
if checkout_count!=persist_count:
    bad(f'checkout credential persistence is not disabled everywhere: checkout={checkout_count} persist_false={persist_count}')


# Dependency updates must go through a tested pull-request path rather than silently
# floating in production.
dependab=ROOT/'.github/dependabot.yml'
if not dependab.exists(): bad('Dependabot maintenance policy missing')
else:
    dep=dependab.read_text(encoding='utf-8')
    if 'package-ecosystem: "pip"' not in dep or 'package-ecosystem: "github-actions"' not in dep: bad('Dependabot must cover pip and github-actions')
release=text('.github/workflows/release-verification.yml')
if re.search(r'(?m)^  pull_request:\s*$',release) is None: bad('release verification must run on pull requests')

# Dependencies in CI are exact, not floating ranges.
for name in ('requirements.txt','requirements-dev.txt'):
    for line in text(name).splitlines():
        line=line.strip()
        if not line or line.startswith('#') or line.startswith('-r '): continue
        if '==' not in line: bad(f'{name}: unpinned dependency: {line}')

# Web executable supply chain: no third-party runtime script, strict CSP on every page.
for path in ROOT.glob('*.html'):
    body=path.read_text(encoding='utf-8')
    if 'http-equiv="Content-Security-Policy"' not in body: bad(f'{path.name}: CSP missing')
    if 'script-src \'self\'' not in body or "object-src 'none'" not in body: bad(f'{path.name}: CSP not restrictive enough')
    if 'name="referrer" content="no-referrer"' not in body: bad(f'{path.name}: referrer policy missing')
    if re.search(r'<script[^>]+src=["\']https?://',body,re.I): bad(f'{path.name}: third-party runtime script')
    if re.search(r'\son[a-z]+\s*=',body,re.I): bad(f'{path.name}: inline event handler blocks strict script CSP')
if (ROOT/'assets/chart-loader.js').exists(): bad('remote chart loader must be removed')

shared=text('assets/shared.js')
if 'safeExternalHref' not in shared or 'url.username||url.password' not in shared: bad('safe external URL gate missing')
if 'https?:\\/\\/' in re.search(r'const newsImageCandidates=.*?;',shared,re.S).group(0): bad('news images still permit HTTP')

# Runtime configuration may contain a public endpoint only after a successful deployment.
runtime=text('assets/runtime-config.js'); sw=text('service-worker.js'); deploy=text('.github/workflows/deploy-live-market-worker.yml'); worker=text('edge/market-live-worker.js'); wrangler=text('edge/wrangler.jsonc.example'); readiness=text('scripts/production_readiness.py'); smoke=text('scripts/browser_smoke.py')
if 'live-runtime/runtime-config.json' not in runtime: bad('runtime config is not deployment-published')
static_match=re.search(r'const STATIC=(\[.*?\]);',sw,re.S)
if static_match and 'runtime-config.js' in static_match.group(1): bad('runtime config is service-worker precached')
for token in ('Fail closed when production authorization is incomplete','environment: production','wranglerVersion: 4.123.0','persist-credentials: false'):
    if token not in deploy: bad(f'deploy hardening missing: {token}')
if 'CLOUDFLARE_API_TOKEN' not in deploy or 'CLOUDFLARE_ACCOUNT_ID' not in deploy: bad('Cloudflare authorization variables missing')
if 'vars.CLOUDFLARE_KV_NAMESPACE_ID' not in deploy or 'secrets.CLOUDFLARE_KV_NAMESPACE_ID' in deploy: bad('KV namespace must have one non-secret configuration source')
# The endpoint must come from the immutable deploy Action output, never from a hand-maintained
# repository variable that can drift from the deployed Worker.
for token in ('id: deploy-worker','steps.deploy-worker.outputs.deployment-url','live_market_endpoint: ${{ steps.endpoint.outputs.url }}','LIVE_MARKET_ENDPOINT: ${{ needs.deploy.outputs.live_market_endpoint }}'):
    if token not in deploy: bad(f'Verified deployment endpoint handoff missing: {token}')
if re.search(r'vars\.LIVE_MARKET_ENDPOINT|secrets\.LIVE_MARKET_ENDPOINT',deploy): bad('live endpoint must not be manually configured in repository secrets/variables')
if 'data/runtime-config.json' not in deploy or 'deployment credentials never published' not in deploy: bad('public runtime publication contract missing')
for token in ('ALLOWED_SYMBOLS','/health','MARKET_CACHE binding unavailable','unsupported symbol or interval','API_RATE_LIMITER','rate_limit_binding','rate limit exceeded'):
    if token not in worker: bad(f'Worker hardening missing: {token}')
expected_host='market-event-radar-live.qwe70542asd.workers.dev'
if expected_host not in runtime or expected_host not in deploy or expected_host not in readiness:
    bad('exact workers.dev hostname allowlist missing from runtime/deploy/readiness')
if '/health' not in runtime or 'live-runtime-verified' not in runtime:
    bad('browser runtime does not verify Worker identity before trust')
if 'RETRY_DELAYS=(0,3,5,10,15,30)' not in readiness or 'get_json_retry' not in readiness:
    bad('post-deploy propagation retry guard missing')
if 'wait_for_function(' in smoke:
    bad('browser smoke still uses CSP-incompatible string eval wait_for_function')
if '"ratelimits"' not in wrangler or '"name": "API_RATE_LIMITER"' not in wrangler:
    bad('Cloudflare Rate Limiting binding missing')
if '"preview_urls": false' not in wrangler or '"workers_dev": true' not in wrangler:
    bad('Worker public route/preview URL policy missing')

# Portfolio import must be bounded/validated.
portfolio=text('assets/portfolio.js')
for token in ('file.size>1024*1024','input.length>500','candidateMap.get(symbol)','quantity>1e12','cost>1e12'):
    if token not in portfolio: bad(f'portfolio import hardening missing: {token}')

# Reject likely accidentally committed credentials/keys. Variable names are fine; literal token shapes are not.
secret_patterns=[
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
    re.compile(r'\bgithub_pat_[A-Za-z0-9_]{40,}\b'),
    re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
    re.compile(r'\bcf(?:ut|at|k)_[A-Za-z0-9_-]{40,100}\b'),
]
for path in ROOT.rglob('*'):
    if not path.is_file() or '.git' in path.parts or path.suffix.lower() in {'.png','.jpg','.jpeg','.webp','.zip'}: continue
    if path.name.startswith('.env') or path.name=='.dev.vars': bad(f'secret-bearing file must not be committed: {path.relative_to(ROOT)}'); continue
    try: body=path.read_text(encoding='utf-8')
    except Exception: continue
    if any(pattern.search(body) for pattern in secret_patterns): bad(f'credential-like literal found: {path.relative_to(ROOT)}')

if FAIL:
    print('SECURITY AUDIT FAILED',file=sys.stderr)
    for item in FAIL: print(' - '+item,file=sys.stderr)
    raise SystemExit(1)
print('security audit ok: immutable Actions, fail-closed deployment auth, CSP, endpoint identity/retry/rate-limit guards, bounded imports, no obvious secrets')
