# v11.4.46 production deployment and authorization

## A. Replace the repository cleanly

1. Pull the latest `main` in GitHub Desktop.
2. Keep the local `.git` directory; replace the project files with the v11.4.46 full ZIP.
3. Run `CLEAN-REPO.cmd`.
4. Confirm GitHub Desktop shows both changed files and intended deletions.
5. Commit and push.
6. Do not accept the release as healthy until `Verify v11.4.46 stable app release` is green.

## B. GitHub Actions security settings

In repository **Settings → Actions → General**:

- set default `GITHUB_TOKEN` workflow permissions to **Read repository contents**;
- enable **Require actions to be pinned to a full-length commit SHA** if the option is available;
- preferably restrict allowed Actions to GitHub-owned Actions plus `cloudflare/wrangler-action`;
- protect `main` against force-push and deletion;
- review Dependabot pull requests and require the `Verify v11.4.46 stable app release` check before accepting dependency updates.

The workflows themselves already use full-SHA pins and explicitly request write permission only for data-publisher workflows.

## C. Cloudflare production authorization

Create a GitHub Environment named `production`. Restrict it to the `main` branch; if your plan supports Environment reviewers, require your own approval before the Cloudflare secrets are released.

Configure these values (repository or Environment scope):

- Secret `CLOUDFLARE_API_TOKEN`
- Secret `CLOUDFLARE_ACCOUNT_ID`
- Variable `CLOUDFLARE_KV_NAMESPACE_ID`

For `CLOUDFLARE_API_TOKEN`, create a Cloudflare custom token based on **Edit Cloudflare Workers** and scope it only to the account used by this project. Do not use the Global API Key and do not commit the token.

The deploy workflow intentionally fails when any required authorization/configuration is missing. “Skipped but green” is not accepted anymore.

## D. Live Worker activation flow

After the three Cloudflare production values exist, run `Deploy v11.4.46 live market worker` (or push a relevant Worker file). The public Worker endpoint is taken automatically from the pinned Wrangler Action `deployment-url` output; do not create or maintain a separate `LIVE_MARKET_ENDPOINT` secret/variable.

The workflow must complete this sequence:

1. fail-closed authorization validation;
2. immutable source checkout with no persisted Git credential;
3. render the KV binding into `wrangler.jsonc`;
4. deploy with pinned Wrangler 4.123.0;
5. derive the public HTTPS endpoint directly from the deploy Action output and validate it;
6. wait/retry for workers.dev propagation, then verify `/health`, `/market-snapshot.json`, 5-minute K-line and arbitrary-symbol rejection;
7. only then publish the verified public endpoint to `live-runtime`.

The browser subsequently retrieves the endpoint from `live-runtime`, requires the exact hostname `market-event-radar-live.qwe70542asd.workers.dev`, and verifies `/health` before trusting it. Cloudflare API credentials are never sent to the browser.

v11.4.46 also adds a native Workers Rate Limiting binding in `edge/wrangler.jsonc.example`. It does not require another GitHub secret or KV namespace.

## E. Expected UI state

When Worker production readiness passes, the six-index section can display `Worker 即時通道・盤中每分鐘刷新` when the actual payload source is Worker and the row is fresh.

If Worker configuration/deployment is missing or unavailable, the page must say `GitHub 備援・非即時` rather than presenting a GitHub snapshot as live data.

The full Taiwan stock/ETF ranking channel is still an official scheduled snapshot and must not be labeled real-time.
