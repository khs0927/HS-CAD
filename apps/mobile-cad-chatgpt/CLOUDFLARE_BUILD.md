# Cloudflare Git build settings

- Repository: `khs0927/HS-CAD`
- Branch: PR 검증 후 `main`, 검증 중에는 `feature/mobile-only-chatgpt-cad-app`
- Root directory: `apps/mobile-cad-chatgpt`
- Build command: `npm run build`
- Deploy command: `npx wrangler deploy`
- Node.js: 22.18 이상

`prebuild`가 `payload/*.txt`를 결합하여 전체 TypeScript/React/Worker 소스를 재현한 후 Vite가 단일 HTML 위젯을 만듭니다.

배포 전 검사:

```bash
npm install
npm run validate
npx wrangler deploy --dry-run
```

배포 후 검사:

```text
GET https://<worker>.workers.dev/health
MCP https://<worker>.workers.dev/mcp
```
