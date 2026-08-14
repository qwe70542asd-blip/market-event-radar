#!/usr/bin/env python3
"""Production-readiness gate for the live market channel.

Static checks always run. --require-live additionally verifies the deployed
HTTPS Worker endpoint, version contract, supported symbols and freshness truth.
"""
from __future__ import annotations
import argparse,json,re,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
import requests

ROOT=Path(__file__).resolve().parents[1]
EXPECTED_SYMBOLS={"^TWII","^DJI","^IXIC","^SOX","^GSPC","^N225"}

def fail(message:str)->None:
    raise SystemExit(f"PRODUCTION READINESS FAILURE: {message}")

def static_checks(version:str)->None:
    runtime=(ROOT/'assets/runtime-config.js').read_text(encoding='utf-8')
    deploy=(ROOT/'.github/workflows/deploy-live-market-worker.yml').read_text(encoding='utf-8')
    worker=(ROOT/'edge/market-live-worker.js').read_text(encoding='utf-8')
    sw=(ROOT/'service-worker.js').read_text(encoding='utf-8')
    if 'live-runtime/runtime-config.json' not in runtime: fail('runtime endpoint is not deployment-published')
    if 'github-fallback-only' not in runtime: fail('runtime fallback is not explicit')
    if 'Fail closed when production authorization is incomplete' not in deploy or 'exit 2' not in deploy: fail('deployment authorization is not fail-closed')
    if 'environment: production' not in deploy: fail('production environment protection missing')
    if 'wranglerVersion: 4.123.0' not in deploy: fail('Wrangler version is not pinned')
    for token in ('id: deploy-worker','steps.deploy-worker.outputs.deployment-url','live_market_endpoint: ${{ steps.endpoint.outputs.url }}','LIVE_MARKET_ENDPOINT: ${{ needs.deploy.outputs.live_market_endpoint }}'):
        if token not in deploy: fail(f'deployment endpoint is not derived from verified Wrangler output: {token}')
    if re.search(r'vars\.LIVE_MARKET_ENDPOINT|secrets\.LIVE_MARKET_ENDPOINT',deploy): fail('live endpoint must not be manually configured')
    if '/health' not in worker or 'ALLOWED_SYMBOLS' not in worker: fail('Worker health/symbol allowlist missing')
    if version not in worker or version not in runtime: fail('runtime/worker version mismatch')
    if 'runtime-config.js' in re.search(r'const STATIC=(\[.*?\]);',sw,re.S).group(1): fail('runtime-config.js must not be precached')
    if 'chart-loader.js' in sw or (ROOT/'assets/chart-loader.js').exists(): fail('remote runtime chart loader still present')
    print('production static readiness ok')

def valid_https_endpoint(endpoint:str)->str:
    endpoint=endpoint.strip().rstrip('/')
    p=urlparse(endpoint)
    if p.scheme!='https' or not p.netloc or p.username or p.password or p.fragment or p.query:
        fail('live market endpoint must be a clean HTTPS origin/path without credentials/query/fragment')
    return endpoint

def get_json(url:str,timeout:int=12):
    r=requests.get(url,headers={'accept':'application/json','user-agent':'MarketEventRadar-readiness/11.4.45'},timeout=timeout)
    r.raise_for_status(); return r.json()

def live_checks(endpoint:str,version:str)->None:
    endpoint=valid_https_endpoint(endpoint)
    try: health=get_json(endpoint+'/health')
    except Exception as exc: fail(f'/health unavailable: {exc}')
    if health.get('version')!=version or health.get('status')!='ok' or health.get('cache_binding') is not True:
        fail(f'health contract invalid: {health}')
    try: snap=get_json(endpoint+'/market-snapshot.json')
    except Exception as exc: fail(f'market snapshot unavailable: {exc}')
    if (snap.get('metadata') or {}).get('version')!=version: fail('snapshot version mismatch')
    rows=snap.get('items') or []
    symbols={str(row.get('symbol') or '') for row in rows}
    if symbols!=EXPECTED_SYMBOLS: fail(f'snapshot symbols mismatch: {sorted(symbols)}')
    now=datetime.now(timezone.utc)
    open_rows=[row for row in rows if row.get('market_open')]
    for row in open_rows:
        stamp=row.get('market_at')
        try: age=(now-datetime.fromisoformat(str(stamp).replace('Z','+00:00'))).total_seconds()
        except Exception: fail(f"invalid live timestamp for {row.get('symbol')}: {stamp}")
        if age>240 and row.get('freshness_status')=='live': fail(f"{row.get('symbol')} claims live at age {age:.0f}s")
    try: kline=get_json(endpoint+'/kline?symbol=%5ETWII&interval=5m')
    except Exception as exc: fail(f'kline endpoint unavailable: {exc}')
    if kline.get('symbol')!='^TWII' or len(kline.get('candles') or [])<2: fail('kline contract invalid')
    # The Worker must reject arbitrary Yahoo proxying.
    try:
        r=requests.get(endpoint+'/kline?symbol=AAPL&interval=5m',timeout=12)
        if r.status_code!=400: fail(f'arbitrary symbol was not rejected (HTTP {r.status_code})')
    except requests.RequestException as exc: fail(f'symbol allowlist probe failed: {exc}')
    print(f'production live readiness ok: {endpoint}')

def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument('--endpoint',default=''); ap.add_argument('--require-live',action='store_true'); ap.add_argument('--version',default='v11.4.45'); args=ap.parse_args()
    static_checks(args.version)
    if args.require_live:
        if not args.endpoint: fail('--require-live requires --endpoint')
        live_checks(args.endpoint,args.version)

if __name__=='__main__': main()
