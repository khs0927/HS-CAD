# HS-CAD Mobile Deployment and Acceptance Result

- Date: 2026-07-16 (Asia/Seoul)
- Branch: `feature/mobile-only-chatgpt-cad-app`
- Validation commit before remote recheck: `c01795b`
- Node.js: 22.18.0 (validation runtime)
- npm: 10.9.2
- Wrangler: 4.110.0
- Python: 3.12.10
- ZWCAD: 2026, active COM connection during connected validation
- Worker URL: `https://hscad-mobile-cad.candy-devourer.workers.dev`
- MCP URL: `https://hscad-mobile-cad.candy-devourer.workers.dev/mcp`
- Current MCP protocol: `2025-11-25`
- Current widget URI: `ui://hscad-mobile/editor-v3.html`
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
| Cloudflare Worker deployment | PASS | public Worker URL issued and serving version 0.3.0 |
| Hosted `/health` | PASS | remote recheck on 2026-07-16 returned `ok:true`, service `hscad-mobile-cad`, schema `1.0`, protocol `2025-11-25`, widget `editor-v3` |
| Hosted `/mcp` reachability | PASS | endpoint returned the expected JSON-RPC transport error when called without `Accept: text/event-stream`, confirming Streamable HTTP enforcement |
| Full hosted MCP smoke | PASS | repository connected-validation record: initialize, tools, resource read and calls |
| Private ChatGPT app registration | PENDING | requires connected ChatGPT Developer Mode session |
| ChatGPT web/mobile acceptance prompts | PENDING | requires private app registration |

## Defects fixed during connected validation

- Reconciled `package.json` and `package-lock.json`, restored the CI/security scripts, and separated Node's built-in tests from Vitest collection.
- Moved the widget URI constant out of the Worker entry module so the Cloudflare runtime no longer treats it as an exported RPC handler.
- Added the missing `ZWCADCOMAdapter.list_texts()` API and a focused regression test after the live COM scan test exposed it.

## Remaining connected-account steps

1. Register `https://hscad-mobile-cad.candy-devourer.workers.dev/mcp` as a private ChatGPT Developer Mode app named `HS-CAD Mobile`.
2. Run every prompt in `MOBILE_TEST_PROMPTS.md` on ChatGPT web and mobile, including SVG/DXF downloads and a dimension-changing follow-up.
3. Record screenshots, download checks, and the final mobile acceptance decision without committing credentials or private user data.

No account identifiers, tokens, cookies, customer drawings, or raw deployment logs are included in this file. The Worker and MCP URLs are intentionally public deployment endpoints.