# Security and privacy

HS-CAD Mobile is a deterministic drawing generator. It accepts only a versioned
`BuildingSpec` object and creates new DXF/SVG artifacts. It does not execute
user-provided JavaScript, Python, shell, AutoLISP, macros, or CAD commands, and
it never edits an uploaded DWG or DXF.

## Trust boundaries

- The public Cloudflare Worker terminates HTTPS and exposes only `/health`,
  `/mcp`, and static PWA assets.
- Every MCP request gets a fresh, stateless `McpServer`; no project data is
  persisted by the application.
- Tool inputs are parsed with strict Zod 4 schemas. Unknown keys, unsupported
  schema versions, non-finite coordinates, invalid wall references, and
  excessive collection sizes are rejected.
- Request bodies, generation time, and generated artifact sizes are bounded.
- Large DXF/SVG strings are widget-only `_meta`; model-visible results contain
  summaries and artifact metadata only.
- SVG text, identifiers, layer names, and DXF text are escaped or normalized
  before serialization.

## Browser policy

The widget uses a minimal MCP Apps CSP and does not load third-party scripts,
fonts, analytics, or arbitrary URLs. Production responses set content-type,
referrer, frame, and browser-permission protections. CORS is not opened with a
wildcard; MCP clients use same-endpoint POST requests.

The PWA uses only local assets. Downloads are produced in-memory in the user's
browser. There is no service worker, background sync, account database, or
telemetry SDK in this version.

## Logging and privacy

Server logs contain a generated request ID, route, method, status, duration,
and bounded error category. They intentionally exclude request bodies,
dimensions, project names, generated drawings, authorization headers, and
download contents. `/health` does not disclose credentials or user data.

## Abuse controls

The application rejects oversized HTTP bodies before parsing, caps polygon,
wall, opening, grid, fixture, and furniture counts, limits coordinate and text
sizes, applies a generation deadline, and rejects output beyond the configured
artifact budget. These controls limit per-request CPU and memory consumption.

For a broadly advertised public endpoint, add a Cloudflare account-level rate
limit keyed by IP or authenticated user at `/mcp` and begin with a conservative
burst allowance. Monitor 429 rates and Worker CPU before changing the limit.
No paid Cloudflare feature is enabled by this repository.

## Dependency and secret checks

Run before release:

```bash
npm ci
npm audit --audit-level=high
npm run check:licenses
npm run scan:secrets
npm run build
npm run check:bundle
```

`check:licenses` reviews every installed package's declared license. The
resolved graph currently contains permissive licenses plus MPL-2.0 and one
Sharp platform package whose bundled libvips components are declared
`Apache-2.0 AND LGPL-3.0-or-later`; redistribution must preserve upstream
notices. `scan:secrets` checks the application and its dedicated workflow
without printing matched values. `check:bundle` rejects source maps, local user
paths, recognizable credential formats, and unexpectedly large output.

## Reporting and rotation

Do not put tokens in an issue, PR, screenshot, or chat. If a credential may have
been exposed, revoke it at the provider, remove it from every reachable Git
object, rotate dependent credentials, and only then publish a sanitized
incident summary.

Generated drawings are for design review. Building code, structural,
fire-safety, accessibility, and construction suitability require qualified
professional review.
