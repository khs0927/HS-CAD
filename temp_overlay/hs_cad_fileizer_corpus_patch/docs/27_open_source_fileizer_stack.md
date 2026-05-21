# 27. Open Source Fileizer Stack

ezdxf, LibreDWG, Docling, Unstructured, PyMuPDF, PaddleOCR, IfcOpenShell, Speckle optional의 역할과 fallback 정책을 정리합니다.

## 원칙

- 원본 도면은 read-only로 처리합니다.
- 외부 도면 스타일은 회사 표준으로 삼지 않습니다.
- 최종 출력 기준은 HS-CAD 내부 CompanyDraftingProfile입니다.
