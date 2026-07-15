# HS-CAD Mobile Deployment and Acceptance Result

- Date: 2026-07-15 (Asia/Seoul)
- Branch: `feature/mobile-only-chatgpt-cad-app`
- Validation commit: `86b950a`
- Node.js: 22.18.0 (validation runtime)
- npm: 10.9.2
- Wrangler: 4.110.0
- Python: 3.12.10
- ZWCAD: 2026, active COM connection
- Worker URL: omitted because deployment is pending
- Intended visibility: private ChatGPT Developer Mode app only

## Validation results

| Check | Result | Evidence |
| --- | --- | --- |
| TypeScript typecheck | PASS | `npm run typecheck` |
| UI and geometry tests | PASS | 43 Vitest tests |
| Bootstrap/deployment contract tests | PASS | 6 Node tests |
| Production UI build and bundle limits | PASS | single-file build, 313,163-byte HTML |
| Cloudflare Worker dry-run | PASS | Wrangler dry-run completed |
| License inventory and secret scan | PASS | 285 packages reviewed; 51 files scanned |
| Local Worker health | PASS | HTTP 200 with `ok: true` |
| Local MCP protocol smoke | PASS | initialize, four tools, resource list/read, valid and invalid calls |
| Widget resource contract | PASS | versioned URI and `text/html;profile=mcp-app` |
| Python unit suite | PASS | 381 passed, 16 environment-gated skipped |
| ZWCAD 2026 COM integration | PASS | 7 passed against a temporary copied DWG |
| XiCAD live integration | NOT RUN | `XICAD_ROOT` is not configured on this computer |
| ZWCAD 2025 integration | NOT RUN | connected installation is ZWCAD 2026 |
| Cloudflare production deployment | BLOCKED | current API token lacks required account/Worker permissions; OAuth needs browser approval |
| Hosted `/health` and `/mcp` smoke | PENDING | requires successful deployment |
| Private ChatGPT app registration | PENDING | requires hosted HTTPS `/mcp` URL and connected ChatGPT browser session |
| ChatGPT web/mobile acceptance prompts | PENDING | requires private app registration |

## Defects fixed during connected validation

- Reconciled `package.json` and `package-lock.json`, restored the CI/security scripts, and separated Node's built-in tests from Vitest collection.
- Moved the widget URI constant out of the Worker entry module so the Cloudflare runtime no longer treats it as an exported RPC handler.
- Added the missing `ZWCADCOMAdapter.list_texts()` API and a focused regression test after the live COM scan test exposed it.

## Remaining connected-account steps

1. Authenticate Wrangler with a token that can deploy Workers and read account membership, or complete `wrangler login` in a connected browser.
2. Run `scripts/deploy_and_verify.ps1 -AllowUncommitted` and confirm the generated local deployment result.
3. Run `npm run smoke:mcp -- https://<worker-host>/mcp` against the deployed endpoint.
4. Register that HTTPS `/mcp` URL as a private ChatGPT Developer Mode app named `HS-CAD Mobile`.
5. Run every prompt in `MOBILE_TEST_PROMPTS.md` on ChatGPT web and mobile, including SVG/DXF downloads and a dimension-changing follow-up.

No account identifiers, tokens, cookies, private endpoint URLs, customer drawings, or raw deployment logs are included in this file.
