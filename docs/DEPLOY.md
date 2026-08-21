# v11.4.49 production deployment

## A. Full replacement

1. Pull latest `main` in GitHub Desktop.
2. Keep the repository `.git` directory only; remove the old working-tree contents.
3. Copy every file/folder from the v11.4.49 full-replacement ZIP into the repository root.
4. Run `CLEAN-REPO.cmd` once.
5. Commit and push.
6. Require `Verify v11.4.49 stable app release` to pass before treating the release as accepted.

## B. Cloudflare production authorization

Existing GitHub Environment / repository values remain:

- Secret `CLOUDFLARE_API_TOKEN`
- Secret `CLOUDFLARE_ACCOUNT_ID`
- Variable `CLOUDFLARE_KV_NAMESPACE_ID`

Do not configure `LIVE_MARKET_ENDPOINT` manually.

The production deploy is fail-closed. The Worker is deployed with the pinned Wrangler Action and then checked through the fixed allowlisted origin:

`https://market-event-radar-live.qwe70542asd.workers.dev`

Production Readiness must validate `/health`, `/market-snapshot.json`, a K-line request and arbitrary-symbol rejection. Browser runtime independently verifies the same `/health` identity/schema contract before enabling the Worker; otherwise it stays on GitHub last-known-good fallback data.

## C. GitHub security settings

Keep default workflow token permissions read-only where possible, protect `main` against force-push/deletion, protect the `production` Environment, and keep external Actions pinned to full commit SHAs. Data-publisher workflows receive write permission only where they publish isolated `live-*` snapshots.

## D. Event calendar

v11.4.49 adds a verified 2026 schedule snapshot for BOJ, ECB, BOE, Taiwan CBC and BOK. These entries are fed through the same event archive/state machine as other official events. A date-only official schedule remains date-only; the application does not invent an announcement time.
