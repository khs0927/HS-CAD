# 모바일만으로 배포하기

## Cloudflare 모바일 브라우저

1. Cloudflare 대시보드에서 Workers & Pages를 엽니다.
2. 저장소 가져오기를 선택합니다.
3. `khs0927/HS-CAD`를 연결합니다.
4. Root directory를 `apps/mobile-cad-chatgpt`로 지정합니다.
5. Build command는 `npm run build`입니다.
6. Deploy command는 `npx wrangler deploy`입니다.
7. Node.js 버전은 22.18 이상으로 지정합니다.
8. 배포 후 `/health`가 `ok: true`를 반환하는지 확인합니다.
9. `/mcp` 주소를 ChatGPT 개발자 모드의 커스텀 앱으로 등록합니다.

무료 모바일 MVP는 Worker 안에서 결정론적 DXF/SVG 생성만 수행합니다. OCR, 이미지 추론, DWG 직접 변환은 별도 고성능 서비스가 필요한 확장 범위입니다.

## 모바일 수락 테스트

```text
HS-CAD 모바일 편집기를 열어줘.
```

```text
가로 12m, 세로 11.3m, 벽 두께 200mm, 처마 3.2m, 용마루 5m, 다락 바닥 2.6m인 박공지붕 건물의 평면도 1면, 입면도 4면, 단면도 2면을 생성해줘.
```

```text
외곽선 폐합, 자기교차, 창호 범위, 다락 유효폭, 지붕 경사를 검증하고 DXF와 SVG를 내려받을 수 있게 해줘.
```

## 정상 배포 확인

- `GET /health`: HTTP 200
- MCP initialize: protocol negotiation 성공
- tools/list: 4개 도구 노출
- resources/read: `text/html;profile=mcp-app`
- 모바일 위젯에서 DXF와 SVG 다운로드 버튼 작동
