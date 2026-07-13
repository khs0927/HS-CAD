# HS-CAD Mobile ChatGPT App v0.2.0

모바일 ChatGPT 또는 모바일 브라우저만으로 건축 도면 세트를 생성하고 검증하는 **ChatGPT App + PWA + Cloudflare Workers MCP 서버**입니다. 로컬 CAD 프로그램이나 Windows PC 없이 SVG 미리보기와 DXF R12 파일을 생성합니다.

## 제공 기능

- 모바일 터치 입력 UI와 고급 JSON 편집
- 평면도 1면
- 박공지붕 입면도 4면
- 횡단면도 A-A와 종단면도 B-B
- 외벽·내벽·문·창·계단·가구·치수·단면기호·북쪽표시
- 입면의 창호 투영, 처마선·용마루·홈통·선홈통·재료 해치
- 단면의 기초·바닥슬래브·벽·천장·다락바닥·지붕두께·서까래·접이식 사다리·레벨
- 건축 면적, 외곽길이, 지붕 경사, 다락 유효폭 계산
- 창호 일람표
- ASCII DXF R12 및 전체 SVG 시트 다운로드
- 외곽선 폐합·자기교차·높이 관계·창호 벽 범위·창 상단 높이 검증
- ChatGPT 후속 메시지와 전체화면 요청
- 위젯 상태 보존 및 자동 높이 보고

## MCP 도구

- `open_mobile_cad`: 편집기 열기
- `render_architectural_set`: 구조화된 도면 데이터를 위젯에 렌더링
- `generate_architectural_set`: 도면 세트와 DXF/SVG 생성
- `validate_architectural_set`: 형상·높이·창호·지붕 조건 검증

## 구조

```text
ChatGPT iOS/Android 또는 모바일 Safari
  → HTTPS Streamable MCP (/mcp)
  → Cloudflare Worker (stateless createMcpHandler)
  → 결정론적 TypeScript CAD 엔진
  → ChatGPT 위젯 SVG + DXF/SVG 다운로드
```

상태 저장이 필요하지 않아 Durable Objects는 사용하지 않습니다. 각 MCP 요청마다 새로운 `McpServer` 인스턴스를 생성합니다.

## 설치와 검증

Node.js 22.18 이상을 사용합니다.

```bash
npm install
npm run validate
npx wrangler deploy --dry-run
```

개별 명령:

```bash
npm run typecheck
npm test
npm run build
npm run dev
npm run deploy
```

## Cloudflare Git 배포

- Root directory: `apps/mobile-cad-chatgpt`
- Build command: `npm run build`
- Deploy command: `npx wrangler deploy`
- Node.js: 22.18 이상

배포 완료 후 MCP 주소는 다음과 같습니다.

```text
https://<worker-name>.<account>.workers.dev/mcp
```

## ChatGPT 모바일 연결

1. ChatGPT 설정에서 **Apps & Connectors → Advanced Settings → Developer mode**를 켭니다.
2. 새 커스텀 앱에 배포된 `/mcp` 주소를 입력합니다.
3. 채팅에서 `HS-CAD 모바일 편집기를 열어줘`라고 요청합니다.

## 설계 안전 원칙

- 원본 DWG/DXF를 수정하지 않습니다.
- 임의 JavaScript, Python, LISP 또는 셸 명령을 실행하지 않습니다.
- 모든 입력은 Zod 스키마로 검증합니다.
- 생성은 허용된 구조화 데이터와 결정론적 함수만 사용합니다.
- 결과는 설계 검토용이며 시공 전 건축·구조·법규 전문가의 확인이 필요합니다.

자세한 검증 결과는 `CONTEXT7_VALIDATION.md`를 확인하세요.
