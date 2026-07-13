# 오픈소스 검토 및 선택 기록

## 런타임에 채택

- **Model Context Protocol TypeScript SDK 1.29.0**: MCP 서버, 도구, 리소스, Streamable HTTP 계약.
- **MCP Apps SDK (`@modelcontextprotocol/ext-apps`) 1.7.4**: `registerAppTool`, `registerAppResource`, `RESOURCE_MIME_TYPE` 및 위젯 메타데이터.
- **Cloudflare Agents 0.17.3 / Workers**: 설치가 필요 없는 stateless MCP 호스팅과 Assets 제공.
- **React 19 + Vite 8**: 터치 친화적 단일 HTML 위젯과 PWA.
- **Zod 4**: 도면 파라미터, 외곽 폴리라인, 벽·문·창 입력 및 도구 결과 검증.

## HS-CAD 기존 자산 재사용

- 기존 `ezdxf` 원칙과 R12 DXF 검증 경험을 TypeScript DXF exporter 설계에 반영했습니다.
- 기존 안전 원칙인 dry-run, 원본 무변경, 허용된 구조화 명령만 실행을 유지합니다.
- 향후 Python remote worker와 동일한 `BuildingSpec` JSON 계약으로 연결할 수 있습니다.

## 검토했으나 MVP 런타임에는 제외

- **ezdxf**: Python 중심이므로 Cloudflare Worker에서 직접 실행하지 않고 고급 검증·PDF 출력 백엔드 후보로 유지합니다.
- **LibreCAD**: 데스크톱 C++ CAD이므로 모바일-only 런타임과 맞지 않지만 결과 검수 기준으로 유용합니다.
- **SVG-Edit**: 범용 브라우저 편집 기능이 크므로 향후 제한된 객체 선택·이동 모드의 참고 대상으로 둡니다.
- **OpenJSCAD**: 박공지붕과 다락 3D 미리보기 후보이나 현재 2D MVP에는 번들·CPU 비용이 큽니다.
- **dxfjs/writer / js-dxf**: 고급 엔티티에 유용하지만 초기 버전은 보안 표면과 번들 크기를 줄이기 위해 내부 ASCII DXF R12 writer를 사용합니다.
- **Maker.js**: 파라메트릭 2D 생성 개념을 검토했으나 핵심 도면 문법을 직접 통제하기 위해 런타임 의존성으로 추가하지 않았습니다.
- **LibreDWG**: DWG 변환 가능성이 있으나 라이선스·배포 조건을 별도로 검토해야 합니다.

## 다음 확장 우선순위

1. dxf-parser 기반 모바일 DXF 불러오기
2. 제한된 터치 객체 편집과 스냅
3. OpenJSCAD 기반 지붕·다락 3D 미리보기
4. ezdxf remote worker 기반 DXF 구조검증과 PDF 출력
5. 라이선스 검토 후 DWG 읽기 전용 변환 실험

외부 CAD 프로젝트의 소스 코드를 복사하지 않았으며, 현재 도면 엔진과 DXF writer는 이 저장소에서 새로 구현했습니다.
