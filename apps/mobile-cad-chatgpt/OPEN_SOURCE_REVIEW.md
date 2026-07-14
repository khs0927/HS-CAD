# Open-source review

Review date: 2026-07-13

All production and test packages are exact versions in `package-lock.json`.
`npm run check:licenses` walks the resolved installed graph rather than checking
only top-level declarations, rejects missing or explicitly disallowed metadata,
and prints a reproducible license summary.

## Runtime choices

- `@modelcontextprotocol/sdk` 1.29.0 — MCP server and protocol contracts.
- `@modelcontextprotocol/ext-apps` 1.7.4 — MCP Apps tools, resources, MIME, and
  widget metadata.
- `agents` 0.17.3 — stateless Cloudflare Streamable HTTP adapter.
- React/React DOM 19.2.7 — accessible mobile widget.
- Zod 4.4.3 — strict runtime contracts.

The production bundle also uses Cloudflare's platform runtime and Workers
Assets. It does not embed a general CAD engine, Python runtime, remote font,
analytics library, or code interpreter.

## Development and independent verification

- Vite 8.1.4, React plugin 6.0.3, and single-file plugin 2.3.3 build the widget.
- TypeScript 5.8.3 and Cloudflare Worker types provide static checks.
- Vitest 4.1.10, Testing Library 16.3.2, User Event 14.6.1, and Happy DOM
  20.10.6 test geometry, protocol, and UI behavior.
- `dxf-parser` 1.1.2 independently parses generated DXF. The production writer
  does not validate its own output and the parser is not shipped at runtime.
- Wrangler 4.110.0 performs local serving, dry-run packaging, and deployment.

## Resolved license review

The automated review currently recognizes 0BSD, Apache-2.0, BSD-2-Clause,
BSD-3-Clause, BlueOak-1.0.0, CC0-1.0, CC-BY-4.0, ISC, MIT, MPL-2.0, Unicode,
Python, and Unlicense identifiers. One optional Sharp Windows platform package
declares `Apache-2.0 AND LGPL-3.0-or-later` because of bundled libvips
components. MPL/LGPL obligations remain limited to their covered components;
upstream notices and corresponding source availability must be preserved when
redistributing those binaries.

`caniuse-lite` browser compatibility data declares CC-BY-4.0. It is a build-time
dependency and is not copied as a standalone database into the application.

`LICENSE-NOTICE.md` is the repository-level handoff. This review is engineering
documentation, not legal advice.

## Evaluated but not adopted in production

- **ezdxf** — excellent independent Python verifier and possible future PDF or
  advanced DXF service, but incompatible with the Worker-only runtime goal.
- **LibreCAD** — useful manual interoperability target, not a mobile runtime.
- **SVG-Edit** — its unrestricted editing surface and bundle are larger than the
  scoped parameter editor requires.
- **OpenJSCAD** — useful future roof/attic 3D preview, unnecessary CPU/bundle
  cost for the seven 2D views.
- **Maker.js**, **dxf-writer**, and **js-dxf** — considered, but direct primitive
  serialization gives this R12 contract tighter ordering and sanitization.
- **LibreDWG** — DWG conversion is outside scope and would require a separate
  license and deployment review.

No source from these CAD projects was copied. The geometry engine, SVG
serializer, and ASCII DXF R12 writer in this directory were implemented for
HS-CAD.

## Release procedure

```bash
npm ci
npm audit --audit-level=high
npm run check:licenses
npm run scan:secrets
```

Re-run the review whenever `package-lock.json` changes. Do not waive a new
license based only on a transitive parent package's license.
