# Cloudflare Git build settings

- Repository: `khs0927/HS-CAD`
- Production branch: select after PR review
- Root directory: `apps/mobile-cad-chatgpt`
- Build command: `npm run build`
- Deploy command: `npx wrangler deploy`
- Node.js: 22

The npm prebuild hook expands the checked-in source bundle into the complete TypeScript/React/Worker project before Vite builds it.
