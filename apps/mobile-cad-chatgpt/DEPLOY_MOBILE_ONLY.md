# 모바일만으로 배포·연결하기

PC 터미널 없이 진행하는 절차입니다.

## 1. GitHub 모바일

- 이 폴더가 포함된 PR을 병합합니다.
- Cloudflare 대시보드에서 GitHub 저장소를 연결하면 GitHub Actions 없이도 빌드할 수 있습니다.

## 2. Cloudflare 모바일 브라우저

- Workers & Pages → Create → Import a repository
- 저장소: `khs0927/HS-CAD`
- Root directory: `apps/mobile-cad-chatgpt`
- Build command: `npm run build`
- Deploy command: `npx wrangler deploy`
- Node version: 22

무료 플랜의 CPU 제한 때문에 OCR, 이미지 추론, DWG 변환은 Worker에서 하지 않고 DXF/SVG 생성만 수행합니다.

## 3. ChatGPT 모바일

- Settings → Apps & Connectors → Advanced Settings → Developer mode
- Create app / Add connector
- MCP server URL: `https://<worker-name>.<account>.workers.dev/mcp`
- 도구가 3개 보이는지 확인

## 4. 첫 테스트 문장

```text
HS-CAD 모바일 편집기를 열고, 가로 12m 세로 11.3m, 처마 3.2m, 용마루 5m, 다락 바닥 2.6m인 박공지붕 건물의 평면도와 입면도 4면, 단면도 2면을 만들어줘.
```
