# Context7 및 통합 검증 보고서

검증일: 2026-07-13

## Context7 확인 결과

### Model Context Protocol TypeScript SDK

- 검증 대상: `/modelcontextprotocol/typescript-sdk/v1.29.0`
- 원격 MCP에는 Streamable HTTP가 권장됩니다.
- 도구는 `McpServer.registerTool()` 또는 Apps SDK의 `registerAppTool()`로 등록합니다.
- 입력·출력 스키마는 Zod 4 기반으로 정의합니다.
- 상태가 필요 없는 서버는 세션과 Durable Object 없이 운영할 수 있습니다.
- HTTP+SSE는 레거시 호환 경로이므로 사용하지 않습니다.

### Cloudflare Agents

- 검증 대상: `/cloudflare/agents`
- `createMcpHandler()`는 Cloudflare Worker에서 stateless MCP를 제공하는 공식 패턴입니다.
- MCP SDK 서버는 한 번 연결된 후 다른 transport에 재사용할 수 없으므로 요청마다 새 `McpServer`를 생성해야 합니다.
- stateless 방식에는 Durable Objects나 migration이 필요하지 않습니다.
- 정적 위젯은 Workers Assets binding으로 제공합니다.

### OpenAI Apps SDK

- 위젯 리소스는 `text/html;profile=mcp-app` MIME 형식과 versioned `ui://` URI를 사용합니다.
- 도구 결과는 모델용 `content`, 모델·위젯 공용 `structuredContent`, 위젯 전용 `_meta`로 구분합니다.
- 렌더링 도구에 `_meta.ui.resourceUri`를 연결합니다.
- 위젯의 CSP는 `_meta.ui.csp`에서 연결·리소스 도메인을 최소 허용합니다.
- `window.openai`를 통해 전체화면, 후속 메시지, 위젯 상태, 자동 높이 보고를 사용합니다.

## 코드 보강 사항

- MCP SDK 1.29.0, ext-apps 1.7.4, Agents 0.17.3, Zod 4.4.3으로 고정
- `registerAppResource`, `registerAppTool`, `RESOURCE_MIME_TYPE` 적용
- versioned UI URI `ui://hscad-mobile/editor-v2.html`
- 요청당 새 MCP 서버 생성
- 표준 `_meta.ui.resourceUri`, `_meta.ui.csp`, `_meta.ui.domain`, `_meta.ui.prefersBorder` 적용
- 생성 전 입력 검증과 구조화된 오류 반환
- `/health` 엔드포인트 추가
- app-only 생성 도구와 모델 노출 도구 분리

## 실제 실행 검증

```text
npm install                         PASS (266 packages audited, 0 vulnerabilities)
npm run typecheck                  PASS
npm test                           PASS (7 tests / 7 passed)
npm run build                      PASS
wrangler deploy --dry-run          PASS
GET /health                        PASS (HTTP 200)
MCP initialize                     PASS (protocol 2025-06-18)
MCP tools/list                     PASS (4 tools)
MCP tools/call validate            PASS
MCP resources/list                 PASS
MCP resources/read widget          PASS
```

빌드 결과:

- 단일 위젯 HTML: 약 235 KB, gzip 약 74 KB
- Worker dry-run upload: 약 2.13 MB, gzip 약 388 KB
- 위젯 MIME: `text/html;profile=mcp-app`
- 총 도면 뷰: 평면 1 + 입면 4 + 단면 2

## 남은 외부 계정 작업

코드·테스트·로컬 MCP 검증은 완료했습니다. 실제 공개 URL 발급은 사용자의 Cloudflare 계정 인증 및 배포 승인이 필요합니다. 이 단계 전까지 PR은 Draft로 유지하는 것이 안전합니다.
