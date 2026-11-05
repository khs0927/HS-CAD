# Cloudflare build settings

- Repository: `khs0927/HS-CAD`
- Production branch: `main`
- Preview branch: `feature/mobile-only-chatgpt-cad-app`
- Root directory: `apps/mobile-cad-chatgpt`
- Build command: `npm run build`
- Deploy command: `npx wrangler deploy`
- Node.js: `22.18.0` or newer
- npm: use the repository lockfile with `npm ci`

All TypeScript, React, CSS, test, Worker, and configuration source is committed
directly. No install or build hook reconstructs source from an opaque payload.
Vite emits a self-contained widget HTML file and the small PWA assets declared
under `public/`; generated `dist`, `.wrangler`, and `node_modules` directories
remain untracked.

## Release gate

```bash
npm ci
npm run typecheck
npm test
npm run build
npm run check:bundle
npm audit --audit-level=high
npm run security:local
npm run check:worker
```

`npm run deploy` repeats the typecheck, tests, build, and bundle inspection
before calling Wrangler. It does not enable Durable Objects, paid storage,
queues, AI inference, or another paid Cloudflare feature.

## Endpoints

```text
GET  https://<worker>.workers.dev/health
POST https://<worker>.workers.dev/mcp
GET  https://<worker>.workers.dev/
```

The MCP server is stateless and creates one SDK server per request. Static files
are supplied by the Workers Assets binding, while `/mcp` and `/health` always run
through the Worker.

## Rollback

Promote the preceding known-good version from **Workers & Pages →
hscad-mobile-cad → Deployments**, or check out the preceding application commit
and run `npm ci && npm run deploy`. Re-run the remote protocol smoke test before
declaring the rollback healthy.
