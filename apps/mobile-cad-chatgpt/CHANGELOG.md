# Changelog

## 0.3.0 — 2026-07-13

### Added

- Readable, reviewable TypeScript/React source in place of the compressed source
  payload bootstrap.
- Versioned `BuildingSpec` contract and expanded architectural entities,
  schedules, metrics, warnings, and seven-view drawing output.
- Independent DXF parsing tests, SVG injection and bounds tests, MCP/HTTP
  contract tests, and mobile widget tests.
- Canonical MCP Apps JSON-RPC bridge support with additive `window.openai`
  feature detection.
- Bundle, license, secret, dependency, and Wrangler dry-run release gates plus a
  path-filtered GitHub Actions workflow.
- Security, testing, deployment, troubleshooting, architecture, and Context7
  validation documentation.

### Changed

- Widget resource URI advanced to `ui://hscad-mobile/editor-v3.html`.
- Model-visible tool output is concise; full DXF and SVG artifacts are delivered
  only to the widget.
- Mobile editing now includes view/layer controls, pan and zoom, validation,
  JSON import/export, individual SVG and combined-sheet downloads, and host
  theme/safe-area handling.
- Worker request handling now enforces input, time, output, method, and response
  security boundaries with request-correlated metadata-safe logs.

### Removed

- `bootstrap.mjs`, base64 payload chunks, and package lifecycle hooks that
  reconstructed source during install or build.

### Compatibility

- Output remains ASCII DXF R12 in millimetres.
- BuildingSpec 1.0 intentionally rejects unsupported schema versions instead of
  silently migrating ambiguous geometry; the widget resource itself is v3.
