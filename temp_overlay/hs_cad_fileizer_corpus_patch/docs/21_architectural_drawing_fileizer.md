# 21. Architectural Drawing Fileizer

DWG/DXF/PDF/이미지/IFC를 원본 수정 없이 JSON/JSONL/Markdown/SQLite로 파일화하는 계층입니다. ezdxf는 DXF 핵심 엔진이고, LibreDWG는 DWG용 외부 CLI adapter로만 사용합니다.

## 원칙

- 원본 도면은 read-only로 처리합니다.
- 외부 도면 스타일은 회사 표준으로 삼지 않습니다.
- 최종 출력 기준은 HS-CAD 내부 CompanyDraftingProfile입니다.
