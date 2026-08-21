#!/usr/bin/env python3
"""Production-readiness gate for the live market channel.

This gate verifies a fixed allowlisted Worker origin. Cache compatibility is
based on schema_version rather than the app release number so an old KV object
cannot poison a new deployment and harmless release bumps do not invalidate a
compatible payload.
"""
from __future__ import annotations
from common import VERSION
import argparse,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
import requests

ROOT=Path(__file__).resolve().parents[1]
EXPECTED_SYMBOLS={"^TWII","^DJI","^IXIC","^SOX","^GSPC","^N225"}
EXPECTED_WORKER_HOST="market-event-radar-live.qwe70542asd.workers.dev"
EXPECTED_SCHEMA="market-snapshot-v2"
RETRY_DELAYS=(0,3,5,10,15,30)
SHORT_RETRY_DELAYS=(0,2,4,8)


def fail(message:str)->None:
    raise SystemExit(f"PRODUCTION READINESS FAILURE: {message}")


def static_checks(version:str)->None:
    runtime=(ROOT/'assets/runtime-config.js').read_text(encoding='utf-8')
    deploy=(ROOT/'.github/workflows/deploy-live-market-worker.yml').read_text(encoding='utf-8')
    worker=(ROOT/'edge/market-live-worker.js').read_text(encoding='utf-8')
    wrangler=(ROOT/'edge/wrangler.jsonc.example').read_text(encoding='utf-8')
    sw=(ROOT/'service-worker.js').read_text(encoding='utf-8') if (ROOT/'service-worker.js').exists() else ''
    if 'live-runtime/runtime-config.json' in runtime or 'publish-runtime:' in deploy:
        fail('obsolete live-runtime publication path is still present')
    if 'direct-worker-verified' not in runtime or 'github-fallback-only' not in runtime:
        fail('direct Worker verification/fallback contract missing')
    if EXPECTED_WORKER_HOST not in runtime or EXPECTED_WORKER_HOST not in deploy:
        fail('exact Worker hostname allowlist missing')
    if 'market-radar:runtime-ready' not in runtime or '/health' not in runtime:
        fail('runtime endpoint health verification missing')
    if EXPECTED_SCHEMA not in runtime or EXPECTED_SCHEMA not in worker:
        fail('market snapshot schema contract missing')
    if 'Fail closed when production authorization is incomplete' not in deploy or 'exit 2' not in deploy:
        fail('deployment authorization is not fail-closed')
    if 'environment: production' not in deploy:
        fail('production environment protection missing')
    if 'wranglerVersion: 4.123.0' not in deploy:
        fail('Wrangler version is not pinned')
    if 'permissions:\n  contents: read' not in deploy:
        fail('deployment workflow must be globally read-only')
    if re.search(r'contents:\s*write',deploy):
        fail('Worker deployment workflow must not publish GitHub runtime branches')
    if re.search(r'vars\.LIVE_MARKET_ENDPOINT|secrets\.LIVE_MARKET_ENDPOINT',deploy):
        fail('live endpoint must not be manually configured')
    for token in ('/health','ALLOWED_SYMBOLS','API_RATE_LIMITER','rate_limit_binding','requesterKey','429','SNAPSHOT_KEY'):
        if token not in worker: fail(f'Worker security/runtime control missing: {token}')
    if '"ratelimits"' not in wrangler or '"name": "API_RATE_LIMITER"' not in wrangler:
        fail('Worker Rate Limiting binding missing')
    if '"preview_urls": false' not in wrangler or '"workers_dev": true' not in wrangler:
        fail('workers.dev/preview URL policy missing')
    if version not in worker:
        fail('Worker version mismatch')
    if 'body?.version===VERSION' in runtime:
        fail('frontend runtime must use schema compatibility instead of exact patch-version coupling')
    static_match=re.search(r'const STATIC=(\[.*?\]);',sw,re.S)
    if static_match and 'runtime-config.js' in static_match.group(1):
        fail('runtime-config.js must not be precached')
    if 'chart-loader.js' in sw or (ROOT/'assets/chart-loader.js').exists():
        fail('remote runtime chart loader still present')
    print('production static readiness ok')


def valid_https_endpoint(endpoint:str)->str:
    endpoint=endpoint.strip().rstrip('/')
    p=urlparse(endpoint)
    if p.scheme!='https' or not p.netloc or p.username or p.password or p.fragment or p.query:
        fail('live market endpoint must be a clean HTTPS origin/path without credentials/query/fragment')
    if p.hostname!=EXPECTED_WORKER_HOST or p.path not in ('','/'):
        fail(f'live market endpoint hostname/path not allowlisted: {p.hostname}{p.path}')
    return endpoint


def get_json(url:str,timeout:int=12):
    r=requests.get(url,headers={'accept':'application/json','user-agent':f'MarketEventRadar-readiness/{VERSION.removeprefix("v")}'},timeout=timeout)
    r.raise_for_status()
    return r.json()


def get_json_retry(url:str,delays=RETRY_DELAYS,timeout:int=12):
    last:Exception|None=None
    for attempt,delay in enumerate(delays,1):
        if delay:
            print(f'readiness retry {attempt}/{len(delays)} in {delay}s: {url}')
            time.sleep(delay)
        try:
            return get_json(url,timeout=timeout)
        except Exception as exc:
            last=exc
            print(f'readiness attempt {attempt}/{len(delays)} failed: {exc}')
    assert last is not None
    raise last


def live_checks(endpoint:str,version:str)->None:
    endpoint=valid_https_endpoint(endpoint)
    try:
        health=get_json_retry(endpoint+'/health')
    except Exception as exc:
        fail(f'/health unavailable after deployment propagation retries: {exc}')
    if health.get('service')!='Market Event Radar live market':
        fail(f'health service identity invalid: {health}')
    if health.get('version')!=version or health.get('schema_version')!=EXPECTED_SCHEMA or health.get('status')!='ok' or health.get('cache_binding') is not True or health.get('rate_limit_binding') is not True:
        fail(f'health contract invalid: {health}')

    try:
        snap=get_json_retry(endpoint+'/market-snapshot.json',SHORT_RETRY_DELAYS)
    except Exception as exc:
        fail(f'market snapshot unavailable after retries: {exc}')
    if (snap.get('metadata') or {}).get('schema_version')!=EXPECTED_SCHEMA:
        fail('snapshot schema mismatch')
    rows=snap.get('items') or []
    symbols={str(row.get('symbol') or '') for row in rows}
    if symbols!=EXPECTED_SYMBOLS:
        fail(f'snapshot symbols mismatch: {sorted(symbols)}')
    now=datetime.now(timezone.utc)
    open_rows=[row for row in rows if row.get('market_open')]
    for row in open_rows:
        stamp=row.get('market_at')
        try: age=(now-datetime.fromisoformat(str(stamp).replace('Z','+00:00'))).total_seconds()
        except Exception: fail(f"invalid live timestamp for {row.get('symbol')}: {stamp}")
        if age>240 and row.get('freshness_status')=='live':
            fail(f"{row.get('symbol')} claims live at age {age:.0f}s")

    try:
        kline=get_json_retry(endpoint+'/kline?symbol=%5ETWII&interval=5m',SHORT_RETRY_DELAYS)
    except Exception as exc:
        fail(f'kline endpoint unavailable after retries: {exc}')
    if (kline.get('metadata') or {}).get('schema_version')!=EXPECTED_SCHEMA or kline.get('symbol')!='^TWII' or len(kline.get('candles') or [])<2:
        fail('kline contract invalid')

    try:
        r=requests.get(endpoint+'/kline?symbol=AAPL&interval=5m',timeout=12)
        if r.status_code!=400:
            fail(f'arbitrary symbol was not rejected (HTTP {r.status_code})')
    except requests.RequestException as exc:
        fail(f'symbol allowlist probe failed: {exc}')
    print(f'production live readiness ok: {endpoint}')


def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--endpoint',default='')
    ap.add_argument('--require-live',action='store_true')
    ap.add_argument('--version',default=VERSION)
    args=ap.parse_args()
    static_checks(args.version)
    if args.require_live:
        if not args.endpoint:
            fail('--require-live requires --endpoint')
        live_checks(args.endpoint,args.version)


if __name__=='__main__':
    main()
