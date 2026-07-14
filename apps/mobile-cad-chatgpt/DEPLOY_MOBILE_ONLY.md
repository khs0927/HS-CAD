# Mobile-only deployment and acceptance

This path needs no Windows PC, desktop CAD application, local Python, or local
MCP server. The repository builds and runs on Cloudflare Workers; deployment and
ChatGPT registration can be completed from a mobile browser.

## 1. Preflight

From `apps/mobile-cad-chatgpt`:

```bash
node --version
npm --version
npm ci
npm run validate
npm audit --audit-level=high
npm run security:local
npm run check:worker
npx wrangler whoami
```

Expected runtime baseline: Node.js 22.18.0 or newer and npm 10.9.3. Do not
continue if typecheck, tests, production build, bundle inspection, high-severity
audit, license/secret checks, or Wrangler dry-run fails.

## 2. Deploy with Wrangler

```bash
npm run deploy
```

Wrangler creates or updates `hscad-mobile-cad` and prints its HTTPS URL. The
configuration uses a stateless Worker and Workers Assets only; it does not
enable Durable Objects, storage, AI inference, or another paid feature.

If a token is present but deployment returns Cloudflare error 10000, update its
account selection and Workers Scripts read/edit permissions under **Cloudflare
profile → API Tokens**. Do not paste the token into chat.

## 3. Optional Cloudflare Git deployment

In **Workers & Pages → Create → Import a repository**:

1. Connect `khs0927/HS-CAD`.
2. Select `main` for production after PR review.
3. Set root directory to `apps/mobile-cad-chatgpt`.
4. Set build command to `npm run build`.
5. Set deploy command to `npx wrangler deploy`.
6. Set Node.js to 22.18.0 or newer.
7. Keep dependency installation locked with `npm ci`.

## 4. Remote acceptance

Replace the origin below with Wrangler's result:

```bash
curl -i https://<worker>.workers.dev/health
node scripts/smoke-mcp.mjs https://<worker>.workers.dev/mcp
```

Accept only when all of these are verified:

- `/health` is HTTP 200 and reports the expected service/widget versions.
- MCP initialize negotiates successfully over Streamable HTTP.
- `tools/list` exposes exactly the four documented tools.
- `resources/list` and `resources/read` return the v3 widget with
  `text/html;profile=mcp-app`.
- Every tool call succeeds for the reference 12,000 × 11,300 mm building.
- Invalid and oversized input fails without leaking the payload.
- The root PWA loads and no source map, local path, token, or development-only
  file is served.

## 5. Connect ChatGPT

When custom MCP apps are enabled for the account, use ChatGPT on the web (the
current documented eligibility surface is web for Pro, Plus, Business,
Enterprise, and Education accounts):

1. Open ChatGPT **Settings**.
2. Open **Security and login** and enable **Developer mode**.
3. Open **Settings → Plugins** or `https://chatgpt.com/plugins`.
4. Select `+` and create a developer-mode Draft app using
   `https://<worker>.workers.dev/mcp`.
5. Start a new chat, open the composer `+` menu, choose **Developer mode**, and
   select HS-CAD.

Success means all four tool names appear, `open_mobile_cad` mounts the Korean
touch editor, and the reference drawing generates seven views. Then ask:

```text
처마 높이를 3.4m로 변경하고 다락 유효폭을 다시 계산해줘.
```

Confirm that the mounted widget updates, metrics change, and DXF, an individual
SVG, combined SVG sheet, and project JSON download on a mobile viewport.

## 6. Mobile viewport checklist

Test 375 × 812, 390 × 844, 430 × 932, a tablet width, embedded ChatGPT, and
full-screen display:

- no horizontal page overflow;
- safe-area padding and approximately 44px touch controls;
- all seven view tabs/selectors accessible;
- pan, zoom, fit, reset, and layer visibility work;
- warnings, schedules, and metrics remain readable in both themes;
- basic and JSON modes validate before generation;
- revision requests and downloads report a clear unsupported-host fallback.

## Free-plan posture

The deployed Worker performs bounded deterministic computation and serves a
small static app. It uses no paid binding. Track request volume, CPU time, bundle
size, and 429/5xx rates in Cloudflare. Before public promotion, configure an
account-level `/mcp` rate limit appropriate for the audience; obtain explicit
approval before enabling any paid feature.

See `TROUBLESHOOTING.md` for authentication, ChatGPT caching, CI billing, DXF
viewer, and rollback procedures.
