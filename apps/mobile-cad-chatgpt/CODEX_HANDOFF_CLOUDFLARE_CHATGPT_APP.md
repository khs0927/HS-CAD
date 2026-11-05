# Codex handoff — Cloudflare deployment and ChatGPT app registration

This document contains the remaining work that requires the user's authenticated Cloudflare and ChatGPT accounts and a connected browser.

The app is intended to remain a private Developer Mode app unless the user separately requests public directory submission.

## Copy this prompt into Codex

```text
Work on repository https://github.com/khs0927/HS-CAD and pull request #127.
Use the existing branch feature/mobile-only-chatgpt-cad-app. Do not create a replacement branch and do not merge the PR.

This task requires my connected computer/browser and my Cloudflare and ChatGPT account sessions. Complete all steps directly. Ask me only for explicit login, account selection, consent, or security approval that cannot be performed without me.

Use $build-chatgpt-app with $openai-docs before changing Apps SDK code or giving product UI instructions. Fetch and follow the current official Apps SDK MCP server, ChatGPT UI, reference, deployment, and Developer Mode connection docs. Prefer current product wording (“app”), while recognizing that some screens may still say “connector”. Do not rely on stale screenshots or guessed menu names.

Primary goals:
1. Run the full local validation on the connected computer.
2. Deploy the existing Cloudflare Worker to a stable public HTTPS workers.dev URL.
3. Verify /health and /mcp from the connected environment.
4. Register the MCP endpoint as a private ChatGPT Developer Mode app.
5. Run the complete mobile acceptance test.
6. Fix only reproducible defects, push safe changes to feature/mobile-only-chatgpt-cad-app, and update PR #127.

A. Prepare the checkout
- Clone or open khs0927/HS-CAD.
- Fetch origin and checkout feature/mobile-only-chatgpt-cad-app.
- Confirm it matches the current PR #127 head.
- Run `git status --short`; do not discard unrelated local work.
- Confirm Node.js is 22.18.0 or newer.

B. Review the implementation before deployment
- Read apps/mobile-cad-chatgpt/README.md, ARCHITECTURE.md, CONTEXT7_VALIDATION.md, OPEN_SOURCE_REVIEW.md, DEPLOY_MOBILE_ONLY.md, and MOBILE_TEST_PROMPTS.md.
- Run a static Apps SDK contract review against current OpenAI docs:
  - reachable Streamable HTTP `/mcp` endpoint;
  - four intended tools and accurate annotations;
  - versioned UI resource URI;
  - `text/html;profile=mcp-app` resource MIME;
  - concise structuredContent and widget-heavy large outputs;
  - CSP/domain metadata appropriate for the actual deployment;
  - no arbitrary JavaScript/Python/LISP/shell execution;
  - no source DWG/DXF mutation.
- If docs now require a code or metadata change, add a regression/static test where practical and make the smallest compatible change before deployment.

C. Validate and deploy with the provided script
From the repository root run:

powershell -ExecutionPolicy Bypass -File apps\mobile-cad-chatgpt\scripts\deploy_and_verify.ps1

The script must:
- verify Node.js version;
- install declared dependencies without running package lifecycle scripts during install;
- run bootstrap security tests, TypeScript checks, Vitest, Vite build, and Wrangler dry-run;
- verify Cloudflare authentication;
- deploy the Worker;
- discover or accept the workers.dev URL;
- retry GET /health until `ok: true`;
- write apps/mobile-cad-chatgpt/CODEX_DEPLOYMENT_RESULT.md.

If Cloudflare authentication is missing, run `npx wrangler login` only after my approval and use my intended Cloudflare account. Never print, copy, or commit access tokens.

If automatic URL discovery fails, rerun with:

powershell -ExecutionPolicy Bypass -File apps\mobile-cad-chatgpt\scripts\deploy_and_verify.ps1 `
  -SkipDeploy `
  -ExpectedWorkerUrl "https://<worker>.workers.dev"

D. Verify the hosted MCP endpoint
- Confirm GET `<worker-url>/health` returns HTTP 200 and `ok: true`.
- Use an MCP inspector or a small protocol client to verify:
  - initialize succeeds with the supported protocol;
  - tools/list exposes exactly the intended four tools;
  - validate_architectural_set returns structured validation data;
  - resources/list and resources/read return the versioned UI resource;
  - the widget resource MIME is `text/html;profile=mcp-app`;
  - repeated read-only calls are safe and deterministic.
- Do not place large DXF/SVG payloads into model-facing content when they belong in the widget/resource path.

E. Register as a private ChatGPT app
- In ChatGPT, use the current official Developer Mode flow. Current docs commonly place this under Settings → Apps & Connectors → Advanced settings, but verify the live UI and official docs first.
- Enable Developer Mode with my approval if it is not already enabled.
- Create a new private app/connector for the remote MCP server.
- Use the public HTTPS MCP URL ending in `/mcp`.
- Give it a clear name such as `HS-CAD Mobile`.
- Keep it private/internal; do not start public app-directory submission.
- Refresh/reconnect the app after any MCP tool descriptor, metadata, UI URI, or CSP change.

F. Run acceptance tests in ChatGPT and mobile browser
Use the prompts in apps/mobile-cad-chatgpt/MOBILE_TEST_PROMPTS.md, plus these checks:
- Open the HS-CAD mobile editor.
- Generate the 12m × 11.3m gable-roof example.
- Confirm one plan, four elevations, and two sections are produced.
- Confirm walls, doors, windows, stairs, furniture, dimensions, section marks, north arrow, roof/eaves/ridge, gutters/downpipes, foundations/slab/ceiling/loft/rafters/levels, and window schedule render.
- Validate polygon closure, self-intersection, window wall indices/ranges, height relationships, roof slope, and loft usable width.
- Test SVG and ASCII DXF R12 download buttons on the mobile browser.
- Open the downloaded DXF in an available CAD viewer and verify expected layers and basic geometry.
- Send a follow-up ChatGPT message that changes one dimension and confirm the widget updates without losing unrelated state.
- Test repeated calls and a deliberately invalid input.
- Capture only privacy-safe screenshots/log summaries. Do not include account identifiers, tokens, or private URLs in committed files.

G. Defect handling
- Distinguish account/UI/deployment configuration problems from code defects.
- For reproducible code defects, add a focused test first when practical, make the smallest fix, rerun `npm run validate:ci`, redeploy, refresh the ChatGPT app, and repeat acceptance tests.
- Do not weaken schema validation, geometry checks, CSP, path safety, or arbitrary-code-execution prohibitions to make a test pass.

H. Safe result documentation
Create or update:
`apps/mobile-cad-chatgpt/DEPLOYMENT_ACCEPTANCE_RESULT.md`

Include only:
- deployment date;
- package/runtime versions;
- sanitized Worker hostname or state clearly that the URL is intentionally omitted;
- health/MCP checks and tool count;
- acceptance test PASS/FAIL table;
- defect/fix commit SHAs;
- remaining limitations;
- confirmation that the app is private Developer Mode only.

Do not include:
- Cloudflare account IDs;
- access tokens/cookies;
- private ChatGPT account data;
- unreviewed deployment logs;
- secrets;
- customer drawing data.

I. Publish safe changes
- Review `git diff` and all generated files for secrets/account data.
- Keep deployment-logs/ and CODEX_DEPLOYMENT_RESULT.md local unless manually sanitized.
- Commit only intended source, tests, and the sanitized DEPLOYMENT_ACCEPTANCE_RESULT.md.
- Push to origin/feature/mobile-only-chatgpt-cad-app.
- Add a PR #127 comment with validation commands, hosted health/MCP status, acceptance totals, commit SHA, and remaining blockers.
- Keep PR #127 Draft if ChatGPT registration or mobile acceptance testing is incomplete.
- Mark ready for review only when validation passes, the deployed endpoint is healthy, the private app loads in ChatGPT, downloads work, and no blocking defect remains.

Stop conditions:
- Do not merge PR #127.
- Do not submit the app publicly.
- Do not purchase a paid plan or paid service.
- Do not expose account credentials or tokens.
- Do not connect unrelated repositories/accounts.
- Do not rewrite unrelated history.
```

## Local-only deployment artifacts

These files may contain account or endpoint information and must remain local until manually reviewed:

```text
apps/mobile-cad-chatgpt/deployment-logs/
apps/mobile-cad-chatgpt/CODEX_DEPLOYMENT_RESULT.md
```

The only intended committed result is the sanitized:

```text
apps/mobile-cad-chatgpt/DEPLOYMENT_ACCEPTANCE_RESULT.md
```
