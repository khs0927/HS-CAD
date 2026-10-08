# Official documentation and Context7 validation

Validation date: 2026-07-13

The implementation was checked against current official OpenAI Apps SDK and
Cloudflare documentation. Context7 was then used for installed-version API
details. Runtime and development dependencies are exact versions in
`package-lock.json`; no range-based install is used for release validation.

## OpenAI Apps SDK

Official pages reviewed:

- Apps SDK quickstart and tool-planning guide
- MCP server, ChatGPT UI, examples, and reference
- deployment, ChatGPT connection, testing, and current Developer mode guides
- security and privacy guide
- current Codex-as-MCP and remote MCP safety documentation

Applied decisions:

- Interactive-decoupled architecture with a small reliable tool set.
- Versioned `ui://hscad-mobile/editor-v3.html` resource using
  `text/html;profile=mcp-app` through `RESOURCE_MIME_TYPE`.
- Standard MCP Apps `ui/*` JSON-RPC bridge is the baseline; documented
  `window.openai` capabilities are feature-detected enhancements.
- Concise `content` and `structuredContent`; complete DXF/SVG values are
  widget-only `_meta`.
- Exact output schemas for model-visible structured results.
- Minimal resource CSP/domain metadata and explicit border preference.
- Current ChatGPT registration path: web **Settings → Security and login →
  Developer mode**, followed by **Settings → Plugins → +** and selection from
  the composer's Developer mode menu.

## Context7 packages checked

### `@modelcontextprotocol/sdk` 1.29.0

Context7 source: `/modelcontextprotocol/typescript-sdk/v1.29.0`

- Remote MCP uses Web Standard Streamable HTTP.
- A stateless endpoint can run without session IDs.
- A transport/server is not reused across independent requests.
- Tool input and output schemas are Zod-compatible object shapes.

### `@modelcontextprotocol/ext-apps` 1.7.4

Context7 source: `/modelcontextprotocol/ext-apps`

- `registerAppTool`, `registerAppResource`, and `RESOURCE_MIME_TYPE` are the
  current server helpers.
- `_meta.ui.resourceUri`, resource CSP/domain metadata, and app/model visibility
  match MCP Apps conventions.
- The UI bridge uses `ui/initialize`, `ui/notifications/initialized`, tool input
  and result notifications, `tools/call`, `ui/message`, and
  `ui/update-model-context`.

### Cloudflare Agents 0.17.3 and Wrangler 4.110.0

Context7 sources: `/cloudflare/agents`, `/cloudflare/workers-sdk`

- `createMcpHandler` is the stateless Worker integration.
- A new `McpServer` is created within every request path.
- Workers Assets is the correct binding for the bundled widget/PWA.
- The selected design needs neither a Durable Object nor a migration.
- Wrangler JSON configuration and dry-run bundle inspection match the installed
  CLI.

### React 19.2.7 and Vite 8.1.4

Context7 sources: `/react/react/v19.2.7`, `/vitejs/vite`

- `createRoot` mounts the widget.
- Host bridge subscriptions use stable external-store/effect cleanup patterns.
- Vite performs the production build; `vite-plugin-singlefile` embeds runtime
  JavaScript and CSS in the resource HTML.

Context7 did not expose a version-specific Vite 8.1.4 page. The current Vite
documentation was combined with the installed CLI/type declarations and an
actual production build.

### Zod 4.4.3

Context7 source: `/websites/zod_dev_v4`

- `z.strictObject` rejects unknown fields.
- finite numeric bounds, collection limits, discriminated unions, and semantic
  refinements enforce the BuildingSpec/tool contracts.
- User-readable issues are derived without echoing drawing payloads.

### `dxf-parser` 1.1.2

Context7 did not contain this package/version. The independent test verifier was
therefore checked against its installed type declarations, package metadata,
and actual parsing behavior. It is test-only and is not shipped in the Worker
runtime.

## Deliberate compatibility metadata

The server emits both MCP Apps `ui` metadata and current OpenAI compatibility
aliases such as `openai/outputTemplate`, invocation text, widget description,
and border preference. These aliases are deliberate for current ChatGPT hosts;
the canonical MCP Apps resource and bridge remain authoritative.

## Reproducible evidence

`TESTING.md` records the final clean-install, type, unit/integration, production
bundle, security, Wrangler, local Worker, remote Worker, and mobile viewport
results. Claims in this document are architecture/API findings, not substitutes
for those executable checks.
