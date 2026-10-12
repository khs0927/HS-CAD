# Troubleshooting

## Installation fails

Confirm the pinned runtime, then reinstall only from the lockfile:

```bash
node --version
npm --version
npm ci
```

The supported baseline is Node.js 22.18.0 or newer and npm 10.9.3. Do not
delete or regenerate `package-lock.json` merely to bypass an integrity error;
inspect the package and lockfile diff first.

## The local Worker does not start

Build the single-file widget before starting Wrangler:

```bash
npm run build
npx wrangler dev --local
```

If `/health` works but the widget resource fails, verify that `dist/index.html`
exists and that Wrangler's `ASSETS` binding points at `dist`. If another process
uses the selected port, pass an unused local port to Wrangler.

## Cloudflare authentication or deployment fails

Check authentication without printing tokens:

```bash
npx wrangler whoami
```

If no account is shown, run `npx wrangler login` in an interactive browser. For
an environment token, grant only the account and Worker permissions required by
Wrangler; never paste the token into chat or commit it. An authentication error
while listing or deploying Workers means the token's Worker read/edit scope or
account selection must be corrected in Cloudflare **My Profile → API Tokens**.

After permissions are corrected:

```bash
npm run deploy
```

## GitHub Actions never starts a job

If the check annotation says the job was not started because recent account
payments failed or the spending limit must be increased, this is not a test
failure. In GitHub open **Settings → Billing & plans**, correct the payment
method or Actions spending limit, then open the failed run and choose
**Re-run jobs → Re-run failed jobs**.

## ChatGPT does not show the tools

1. Confirm the public URL returns HTTP 200 at `/health`.
2. Run the remote MCP smoke test against the exact HTTPS `/mcp` URL.
3. On ChatGPT web, enable Developer mode under **Settings → Security and
   login**. Current official eligibility covers Pro, Plus, Business,
   Enterprise, and Education accounts on the web.
4. Open **Settings → Plugins** (or `chatgpt.com/plugins`), remove a stale Draft,
   select `+`, and add the exact `/mcp` URL again.
5. Start a new chat and select **Developer mode → HS-CAD** from the composer `+`
   menu.

The expected tool names are `open_mobile_cad`, `render_architectural_set`,
`generate_architectural_set`, and `validate_architectural_set`.

## The PWA shows an older interface

Close all installed and browser tabs, remove the installed PWA, clear site data
for the Worker origin, and reopen the public URL. This version does not register
a service worker, so stale UI usually comes from the browser or ChatGPT resource
cache. The versioned `ui://` resource URI prevents reuse across releases.

## A DXF looks different in CAD software

The exporter targets ASCII DXF R12 and uses primitive lines, polylines, arcs,
circles, and text. Units are millimetres by contract; some R12 viewers ignore
unit metadata and require manual millimetre selection. Native associative
dimensions, hatches, layouts, paper space, custom fonts, and DWG conversion are
outside this release. Import into a copy, never over an original drawing.

## Rollback

Use Cloudflare's deployment history to promote the last known-good Worker
version, or redeploy the preceding Git commit from this directory. Then restore
the corresponding versioned widget URI in ChatGPT if necessary and repeat the
remote smoke test. Do not roll back only the static widget or only the MCP
server; their tool result contract is version-coupled.
