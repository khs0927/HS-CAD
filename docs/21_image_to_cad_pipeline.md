# Image/PDF to Editable CAD Draft Pipeline

이 모듈은 완전 자동 CAD 완성기가 아니라 **수정 가능한 CAD 초안** 생성기이다.

`src/neuro_seq_cad/`는 기존 HS-CAD의 ZWCAD DWG 편집/문법 학습 엔진과 분리되어 있다. 기존 DWG를 직접 수정하지 않고, 이미지/PDF에서 독립 DXF를 생성한다. 기존 DWG에 적용할 때는 block preview 또는 QA-REVIEW 격리 레이어로 넣는 방식이 안전하다.

## Scope

- Raster2Seq는 polygon sequence vectorization 핵심 후보이지만 optional adapter다.
- Img2CADSeq는 3D STEP 확장 감시 대상이고 2D 평면도 핵심 의존성이 아니다.
- PlanParser/YOLO는 라이선스 이슈 때문에 optional plugin이다.
- 상업 사용 전 Raster2Seq, PlanParser, MLSD, Ultralytics YOLO, OCR 엔진 license 및 라이선스 검토가 필요하다.

## Drafting Policy

- `900mm` 문 폭은 절대값이 아니라 `800/850/900/1000mm` fallback 후보 중 하나다.
- 벽체 두께는 실제 이중선 감지, Raster2Seq polygon, 표준 offset 순서로 결정한다.
- centerline DXF와 wallsolid DXF를 동시에 출력한다.
- `RAW_LINES`, `AI_LOWCONF`, `QA_MARKUP` 레이어를 보존한다.
- `WAL_HATCH`는 벽 outline과 분리한다. hatch를 삭제해도 벽 outline은 남아야 한다.

## Commands

```bash
python -m neuro_seq_cad.app.cli make-sample --out samples/sample_plan.png
python -m neuro_seq_cad.app.cli analyze samples/sample_plan.png --out outputs/demo
python -m neuro_seq_cad.app.cli export-dxf samples/sample_plan.png --out outputs/demo
python -m neuro_seq_cad.app.cli overlay samples/sample_plan.png --out outputs/demo/overlay.png
```

## Outputs

- `outputs/demo/result_centerline.dxf`
- `outputs/demo/result_wallsolid.dxf`
- `outputs/demo/result.json`
- `outputs/demo/overlay.png`
- `outputs/demo/qa_report.md`

모든 실패, 저신뢰, 미확정 판단은 `result.json`과 `qa_report.md`에 기록한다.

