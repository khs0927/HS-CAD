# 오픈소스 검토 및 선택 기록

## 런타임에 채택

- **Model Context Protocol SDK**: ChatGPT 도구와 UI resource 제공.
- **Cloudflare Agents / Workers**: 설치가 필요 없는 모바일용 MCP 호스팅.
- **React + Vite**: 터치 친화적 단일 HTML 위젯과 독립 PWA.
- **Zod**: 도면 파라미터와 좌표 입력 검증.

## HS-CAD 기존 자산 재사용

- 기존 `ezdxf` 원칙과 R12 DXF 검증 경험을 TypeScript DXF exporter 설계에 반영.
- 기존 안전 원칙인 dry-run, 원본 무변경, 허용된 구조화 명령만 실행을 유지.
- 향후 Python remote worker와 동일한 `BuildingSpec` JSON 계약으로 연결 가능.

## 검토했으나 MVP 런타임에는 제외

- **ezdxf**: 가장 강력한 DXF 라이브러리지만 Python 중심이고 Cloudflare Worker에서 직접 실행하기 어렵습니다. 고급 DXF 검증용 백엔드 후보입니다.
- **LibreCAD**: 완성도 높은 2D CAD이나 데스크톱 C++ 앱이므로 모바일-only 조건과 맞지 않습니다.
- **SVG-Edit**: 브라우저 편집기로 유용하지만 일반 그래픽 기능이 크고 건축 파라메트릭 모델과 도면 레이어 계약이 약합니다. 향후 수동 편집 모드 후보입니다.
- **OpenJSCAD**: 브라우저 3D 생성에 유용하나 현재 2D 도면 세트 MVP에는 번들·CPU 비용이 큽니다. 향후 박공지붕 3D 미리보기 후보입니다.
- **dxfjs/writer, js-dxf**: 기능은 풍부하지만 Cloudflare 무료 번들 크기와 API 안정성을 위해 초기 버전은 작은 내부 R12 writer를 사용합니다. 향후 고급 엔티티·블록 지원 시 어댑터로 교체 가능합니다.
- **Maker.js**: SVG/DXF 파라메트릭 생성에 적합하지만 프로젝트 유지 상태와 추가 번들 의존성을 고려해 핵심 구조만 참고했습니다.

## 다음 오픈소스 확장 우선순위

1. dxf-parser 기반 모바일 DXF 불러오기
2. SVG-Edit의 캔버스/선택 UI를 제한적으로 포팅
3. OpenJSCAD로 지붕·다락 3D 미리보기
4. ezdxf remote worker로 DXF 구조 검증 및 PDF 출력
5. LibreDWG는 라이선스·배포 조건 검토 후 읽기 전용 변환 실험
