# HS-CAD Mobile ChatGPT App

모바일 기기만으로 건축 평면도, 박공지붕 입면도 4면, 단면도 2면을 생성하고 DXF/SVG로 내려받는 ChatGPT App + PWA입니다.

## 모바일 전용 운영 구조

```text
ChatGPT iOS/Android 또는 모바일 Safari
  → Cloudflare Workers의 /mcp
  → HS-CAD TypeScript 파라메트릭 도면 엔진
  → ChatGPT 위젯 SVG 미리보기
  → 사용자 기기에 DXF/SVG 다운로드
```

PC CAD, 로컬 Python, ZWCAD, Rhino, Windows 서버가 없어도 기본 도면 생성이 됩니다. DWG 직접 작성은 클라우드에서 라이선스와 변환기가 필요하므로 무료 MVP는 DXF를 표준 산출물로 사용합니다.

## 구현 기능

- 터치 친화적 React UI
- ChatGPT Apps SDK/MCP 도구
  - `open_mobile_cad`
  - `generate_architectural_set`
  - `validate_architectural_set`
- 건물 가로·세로·벽 두께·처마·용마루·다락 높이 입력
- 선택 가능한 용마루 방향
- 선택적 외곽 폴리라인, 내부 벽, 문·창 좌표 입력
- 평면도 1면, 입면도 4면, 단면도 2면
- 브라우저 내 SVG 미리보기
- ASCII DXF R12 다운로드
- 전체 SVG 시트 다운로드
- PWA 설치 가능
- OpenAI API 키 불필요

## 로컬 개발

```bash
cd apps/mobile-cad-chatgpt
npm install
npm run typecheck
npm test
npm run dev
```

## Cloudflare 무료 배포

```bash
npm run deploy
```

배포 후 `https://<worker>.workers.dev/mcp`를 ChatGPT 개발자 모드의 앱 연결 주소로 사용합니다.

## 모바일에서 연결

1. ChatGPT 설정에서 **Apps & Connectors → Advanced Settings → Developer mode**를 켭니다.
2. 새 커스텀 앱을 추가합니다.
3. MCP URL에 Worker의 `/mcp` 주소를 입력합니다.
4. 채팅에서 “HS-CAD 모바일 편집기를 열어줘”라고 요청합니다.

## 안전 경계

- 원본 DWG를 수정하지 않습니다.
- 임의 코드나 LISP를 실행하지 않습니다.
- 도면 생성은 결정론적 JSON/TypeScript 함수만 사용합니다.
- 무료 모바일 MVP는 DXF/SVG 내보내기만 지원합니다.
- 시공용 확정 전 건축사와 구조·법규 검토가 필요합니다.
