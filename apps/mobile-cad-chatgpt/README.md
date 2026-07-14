# HS-CAD Mobile ChatGPT App 0.3.0

Windows PC나 로컬 CAD/MCP 서버 없이 모바일 ChatGPT와 브라우저에서 건축
도면을 생성·검토하는 **ChatGPT App + PWA + Cloudflare Worker**입니다.
결정론적 TypeScript 엔진이 새 ASCII DXF R12와 SVG를 만들며, 업로드한
DWG/DXF를 수정하거나 사용자 코드를 실행하지 않습니다.

## 결과물

- 평면도 1면
- 정면·배면·좌측면·우측면 입면도 4면
- 횡단면도 A-A와 종단면도 B-B
- DXF R12 전체 도면, 개별 SVG 7개, 결합 SVG 시트
- 문·창호 일람표, 도면/레이어 목록
- 면적, 외곽길이, 지붕 경사(각도·비), 다락 유효폭과 경고 요약

평면에는 외벽·내벽·실제 개구·문짝/스윙·창틀·계단·그리드·단면기호·
가구/위생기구·치수·북쪽표시를 포함합니다. 입면은 벽에 연결된 개구를
투영하고, 단면은 기초·슬래브·벽·천장·다락바닥·지붕 구성·레벨·다락
접근을 표현합니다.

모바일 UI는 일곱 뷰 선택, 레이어 표시, 팬/확대/맞춤/초기화, 기본·고급
입력, BuildingSpec JSON 가져오기/내보내기/복사, 경고·일람표·지표,
DXF/SVG 다운로드, GPT 수정 요청을 제공합니다. 44px 터치 영역, safe area,
라이트/다크 호스트 테마와 전체화면 위젯을 고려했습니다.

## 구조

이 앱은 `interactive-decoupled` 형태입니다.

```text
ChatGPT / 모바일 PWA
        ↓ HTTPS Streamable MCP
Cloudflare Worker (/mcp, 요청마다 새 McpServer)
        ↓ strict BuildingSpec 1.0
결정론적 CAD 엔진 → 7 views → DXF/SVG
        ↓ concise structuredContent + widget-only artifacts
MCP Apps widget (ui://hscad-mobile/editor-v3.html)
```

서버 상태가 없으므로 Durable Object, 데이터베이스, 저장소, 레거시
HTTP+SSE를 사용하지 않습니다. 자세한 계약은 `ARCHITECTURE.md`에 있습니다.

## MCP 도구

| 이름 | 용도 |
| --- | --- |
| `open_mobile_cad` | 기본 터치 편집기를 엽니다. |
| `render_architectural_set` | 전달받은 치수/구성을 생성해 위젯에 표시합니다. |
| `generate_architectural_set` | 열린 위젯에서 편집된 데이터를 다시 계산합니다. |
| `validate_architectural_set` | 형상, 높이, 벽 참조, 개구, 지붕, 다락, 출력 무결성을 검사합니다. |

모델에는 짧은 설명·지표·경고·일람표·아티팩트 메타데이터만 보입니다.
큰 DXF/SVG 문자열과 전체 엔티티는 위젯 전용 `_meta`로 전달합니다.

## BuildingSpec 1.0

단위는 `mm`로 고정합니다. 계약은 건물·지붕·기초·슬래브·다락·축척·
재료, 닫힌 외곽 폴리곤, ID가 있는 벽, 방/그리드/단면선, 벽 ID에 연결된
문·창·다락창·벤트, 방향성 계단/다락사다리, 선택적 기둥·가구·설비·
라벨을 지원합니다.

최소 예:

```json
{
  "schemaVersion": "1.0",
  "projectName": "HS-CAD SAMPLE",
  "unit": "mm",
  "width": 12000,
  "depth": 11300,
  "wallThickness": 200,
  "ceilingHeight": 2500,
  "eaveHeight": 3200,
  "ridgeHeight": 5000,
  "atticFloorHeight": 2600,
  "roofDirection": "ridge-along-depth"
}
```

생략한 필드만 문서화된 기본값을 받습니다. 명시한 빈 배열은 빈 상태를
유지하고, 지원하지 않는 버전·고아 벽 참조·불가능한 높이/형상은 조용히
보정하지 않고 오류로 반환합니다.

## 로컬 개발

Node.js 22.18.0 이상과 npm 10.9.3을 사용합니다.

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

로컬 Worker:

```bash
npm run build
npx wrangler dev --local
```

`npm run deploy`는 타입, 테스트, 빌드, 번들 검사를 다시 통과한 뒤 실제
Cloudflare 배포를 수행합니다. 실행 증거와 테스트 수는 `TESTING.md`,
보안·개인정보 보호는 `SECURITY.md`를 확인하세요.

## Cloudflare와 ChatGPT 연결

Cloudflare Git 설정:

- Root directory: `apps/mobile-cad-chatgpt`
- Build command: `npm run build`
- Deploy command: `npx wrangler deploy`
- Node.js: `22.18.0` 이상

배포 후 공개 `https://<worker>.workers.dev/mcp`를 사용합니다. 현재 공식
절차는 지원 요금제의 ChatGPT **웹**에서 **Settings → Security and login →
Developer mode**를 켠 다음 **Settings → Plugins**(또는
`chatgpt.com/plugins`)의 `+` 버튼으로 이 `/mcp` URL을 Draft 앱에 추가하는
것입니다. 새 채팅의 `+` 메뉴에서 **Developer mode**와 앱을 선택한 뒤
다음처럼 요청합니다.

```text
가로 12m, 세로 11.3m, 처마 3.2m, 용마루 5m, 다락 바닥 2.6m인
박공지붕 건물의 HS-CAD 모바일 편집기를 열어줘.
```

구체적 배포·모바일 수락 절차는 `DEPLOY_MOBILE_ONLY.md`, 문제 해결과
롤백은 `TROUBLESHOOTING.md`에 있습니다.

## DXF 범위와 안전 고지

DXF는 millimetre 계약의 ASCII R12이며 LINE, POLYLINE/VERTEX, ARC, CIRCLE,
TEXT 같은 호환성 높은 primitive를 사용합니다. 연관 치수, paper space,
사용자 폰트, 고급 HATCH, IFC/BIM, DWG 변환은 포함하지 않습니다.

결과는 설계 검토용입니다. 시공 전에 해당 지역의 건축·구조·소방·
접근성·인허가 전문가가 치수, 구조, 재료, 법규 적합성을 확인해야 합니다.
