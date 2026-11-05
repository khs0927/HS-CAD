# Third-party notice

HS-CAD Mobile uses npm packages under their respective licenses, including the
Model Context Protocol SDK and Apps SDK, Cloudflare Agents and Wrangler, React,
Zod, Vite, Vitest, Testing Library, Happy DOM, and `dxf-parser`. Preserve the
license and notice files delivered with the resolved packages.

The installed development graph includes `caniuse-lite` data under CC-BY-4.0
and a Sharp Windows optional platform package declared
`Apache-2.0 AND LGPL-3.0-or-later` because of libvips components. See
`OPEN_SOURCE_REVIEW.md` and the packages' own notices before redistributing
build tooling or platform binaries.

The HS-CAD architectural geometry engine and internal ASCII DXF R12 writer are
implemented in this repository and do not copy source from the evaluated CAD
projects. Run `npm ci && npm run check:licenses` against the lockfile before
each public release.
