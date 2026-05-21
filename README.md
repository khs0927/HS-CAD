# ZWCAD AI Architectural Modifier

Windows + ZWCAD 환경에서 기존 DWG 도면을 열고, 객체를 스캔하고, 좌표/레이어/블록/문자 정보를 JSON으로 추출한 뒤, 안전하게 검증된 JSON 명령으로 도면을 수정하는 Python 프레임워크입니다.

## 목표

- ZWCAD에서 기존 DWG 열기
- ModelSpace 객체 전체 스캔
- LINE, POLYLINE, TEXT/MTEXT, BLOCK, CIRCLE 등 주요 객체를 JSON화
- 레이어, 블록, 문자, 경계 폴리라인 분석
- 허용된 JSON 명령만 실행
- 수정 전 백업 생성
- dry-run/preview 모드 지원
- 수정 전후 리포트 생성
- 새 DWG로 저장

## 엔진 구조

1. **메인 후보: PyRx / cad-pyrx**
   - ZWCAD ZRX 2025–2027 기반 고급 객체 제어용
   - 현재는 Adapter 뼈대 제공
   - 실제 설치 환경에 맞춰 `src/adapters/pyrx_adapter.py` 확장

2. **실제 MVP 동작 엔진: ZWCAD COM / ActiveX**
   - `comtypes`로 `ZWCAD.Application` 연결
   - DWG 열기, 저장, ModelSpace 스캔, 레이어 이동, 문자 치환 지원

3. **선택 보조: pyzwcad**
   - 설치되어 있으면 사용 가능하도록 래퍼 제공
   - 실패 시 COM Adapter로 fallback 권장

4. **검증 보조: ezdxf**
   - DXF 분석, 테스트 도면 생성, 비교 검증용
   - 최종 DWG 수정은 ZWCAD 내부 API/COM/PyRx 사용

## 설치

> Windows + ZWCAD 설치 환경에서 실행하세요.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

선택 설치:

```bash
pip install pyzwcad
pip install cad-pyrx
```

`cad-pyrx`/PyRx는 ZWCAD 버전, Python 버전, ZRX 환경에 따라 별도 설정이 필요할 수 있습니다.

## 기본 실행

```bash
python -m src.main --help
python -m src.main scan --dwg "C:/project/sample.dwg" --out "outputs/objects.json"
python -m src.main layers --dwg "C:/project/sample.dwg"
python -m src.main blocks --dwg "C:/project/sample.dwg"
python -m src.main texts --dwg "C:/project/sample.dwg"
```

명령 JSON dry-run:

```bash
python -m src.main run-command --dwg "C:/project/sample.dwg" --command "examples/commands/move_layer.json" --dry-run
```

실제 실행:

```bash
python -m src.main run-command --dwg "C:/project/sample_copy.dwg" --command "examples/commands/move_layer.json" --execute
```

## 안전 규칙

- 실제 수정 전 반드시 원본 DWG를 복사하세요.
- 수정 명령은 기본적으로 백업을 생성합니다.
- `--dry-run`은 실행 계획만 보여줍니다.
- `delete_layer_objects` 같은 삭제 명령은 초기 버전에서 실제 삭제를 막거나 강한 경고를 냅니다.
- AI는 Python 코드를 직접 실행하지 않고, 허용된 JSON 명령만 생성해야 합니다.
- 기존 사무소 DWG를 편집할 때는 샘플링한 주변 레이어와 시각 문법을 우선 사용합니다.
- 사용자가 명시적으로 요청하지 않는 한 기존 레이어를 리맵하지 않습니다.
- 명시적 생성 레이어는 독립 생성 도면 또는 검수 격리 워크플로우에서만 사용합니다.

## 명령 JSON 예시

```json
{
  "command": "move_layer",
  "params": {
    "layer": "A-WALL",
    "dx": 100,
    "dy": 0,
    "dz": 0
  },
  "safety": {
    "backup_required": true,
    "preview_required": true
  }
}
```

## 현재 MVP 지원

- ZWCAD COM 연결
- DWG 열기/저장
- 객체 스캔
- JSON 내보내기
- 레이어별 객체 수 집계
- 블록명별 수량 집계
- 문자 추출
- 특정 레이어 전체 이동
- 문자 일괄 치환
- 건축용 planned actions 생성: 바운더리, 그리드, 기둥 배치 계획

## 향후 개발

- PyRx/cad-pyrx 실제 ZWCAD ZRX 연동
- BlockReference 교체 실행
- Polyline vertex 직접 수정
- LISP 실행 연동 강화
- ZWCAD .NET/ZRX Add-in 패널화
- AI 명령 서버/MCP 연동
- AutoCAD/GstarCAD/BricsCAD Adapter 추가


## XiCAD 연동 추가

이 버전은 업로드된 XiCAD 패키지 구조를 기준으로 `XiCADAdapter`를 추가했습니다. XiCAD는 대부분 컴파일된 LISP/FAS/ZELX 명령 묶음이므로 내부 코드를 직접 수정하지 않고, ZWCAD 명령줄에 XiCAD 명령 alias를 안전하게 큐잉하는 방식으로 연동합니다.

예시:

```bash
python -m src.main xicad-catalog --shortkey "C:/xicad/Lisp/xiShortkey_origin.key"
python -m src.main load-xicad --dwg "C:/cad/sample.dwg" --xicad-root "C:/xicad"
python -m src.main run-xicad --dwg "C:/cad/sample.dwg" --xicad-root "C:/xicad" --load-first --alias WAL
python -m src.main run-command --dwg "C:/cad/sample.dwg" --command "examples/commands/run_xicad_wall.json" --dry-run
```

자세한 내용은 `docs/06_xicad_integration.md`를 보세요.

## XiCAD Safe Bridge Add-on

이 최종 패키지는 `src/extensions/xicad_safe_bridge/`를 포함합니다. Safe Bridge는 기존 `XiCADAdapter`나 `run-xicad` 명령을 덮어쓰지 않고, AI가 XiCAD 명령을 실행하기 전 별도 안전 계획을 만드는 격리형 확장 레이어입니다.

역할:

- XiCAD alias 허용 목록 관리
- WAL, COL, D1, W1, PK, STP, ELV, INS 등 건축 명령 분류
- 대화형 명령 차단 또는 허용 판단
- dry-run preview 생성
- `allow_interactive`, `allow_high_risk` 안전 플래그 검증
- ZWCAD Adapter에는 최종적으로 `run_command()`만 호출

Safe Bridge 명령 예시:

```bash
python -m src.main xicad-safe-catalog
python -m src.main xicad-safe-plan examples/commands/xicad_safe_wall_plan.json
python -m src.main xicad-safe-run --dwg "C:/cad/sample.dwg" --command "examples/commands/xicad_safe_wall_plan.json"
```

실제 실행은 JSON이 `xicad_safe_execute`이고, `safety.allow_interactive=true`이며, CLI에서 `--execute`를 명시해야 가능합니다.

```bash
python -m src.main xicad-safe-run --dwg "C:/cad/sample_copy.dwg" --command "examples/commands/xicad_safe_wall_execute.json" --execute --xicad-root "C:/xicad" --save-as "C:/cad/sample_xicad.dwg"
```

`run-command`도 `xicad_safe_plan` / `xicad_safe_execute` JSON을 인식합니다.

```bash
python -m src.main run-command --dwg "C:/cad/sample.dwg" --command "examples/commands/xicad_safe_wall_plan.json" --dry-run
```

자세한 내용은 `docs/08_xicad_safe_bridge.md`를 보세요.

## Drawing Grammar Learning (도면 작성 문법 학습)

본 엔진은 도면을 강제로 수정하거나 표준화하는 기존 방식을 넘어서, 특정 건축 사무소(지움건축 - ZIUM)의 실무 도면 작성 문법(Drawing Grammar)을 자동 분석하고 학습하여 도면 수정 및 작성 시 정합성을 유지합니다.

### 📌 핵심 원칙
1. **레이어 무변경 관찰 (Layer Integrity)**: 기존 레이어 구조(예: `wall1`, `중심선`, `치수`)를 절대 임의로 변경하지 않고, 신규 객체 배치 시 해당 레이어의 존재를 감지해 동일 레이어로 얹는 가이드라인으로 활용합니다.
2. **도곽 재사용 (Title Sheet Reuse)**: 임의의 도각선 생성 대신, 도면 내 표준 도곽 블록(`ZIUM_sheet_architect`)을 탐색하여 삽입 원점 및 축척을 자동으로 바인딩합니다.
3. **주변 속성 샘플링 (Drafting Attributes Sampling)**: 신규 객체의 색상, 선종류, 선가중치, 텍스트 크기, 치수 스타일은 주변 개체 속성을 실시간 샘플링하여 완벽하게 수렴시킵니다.

### 🚀 문법 학습 관련 도구 실행
* **실시간 도면 레이어/블록 고속 스캔**:
  ```bash
  python tools/fast_scan_active.py
  ```
  ZWCAD 활성 창의 레이어 및 블록 정보를 초고속 스캔하고 JSON 리포트를 작성합니다.
  
* **도면 선/스타일 문법 실시간 샘플링**:
  ```bash
  python tools/analyze_active_form_sample.py
  ```
  활성 도면 내 선, 블록, 문자, 치수, 리더, 도곽 삽입 문법을 샘플링하여 JSON 리포트로 저장합니다.

* **선택 객체 주변 로컬 문법 샘플링**:
  ```bash
  python tools/sample_style_near_handle.py --handle <HANDLE> --radius 3000 --out-dir outputs/style_sample_current
  ```
  특정 객체 주변의 레이어, 색상, 선종류, 선가중치, 문자높이, 치수스타일, 블록 EffectiveName을 샘플링하여 새 객체 생성 시 우선 사용할 로컬 문법을 추천합니다.

* **ZIUM 도곽 사용 가능 영역 측정**:
  ```bash
  python tools/measure_zium_sheet_usable_area.py --out-dir outputs/zium_sheet_area_current
  ```
  `ZIUM_sheet_architect` 블록의 삽입 스케일과 정의 extents를 분석하여 새 도면을 배치할 usable drawing area 후보를 계산합니다.

자세한 내용은 [18. 도면 작성 문법 학습 베이스라인](docs/18_architectural_drawing_learning_baseline.md), [19. 지움 도각 및 선 표현 문법 지침서](docs/19_zium_sheet_and_line_grammar.md), [20. 도면 문법 기반 생성 절차](docs/20_generation_from_drawing_grammar.md)를 참고하세요.

## Added after Codex integration report

This package now includes the next-step architecture audit and safer execution layer:

- `analyze-architecture` CLI for layer/block/text/polyline quality reports
- COM fallback methods for `replace_block`, `delete_layer_objects`, `create_line`, `create_polyline`, `insert_block`
- `place_beams_2d` planned/executable action generation
- XiCAD Safe Bridge remains isolated under `src/extensions/xicad_safe_bridge/`
- `docs/07_windows_test_plan.md` and `docs/09_next_development_plan.md`

Always test mutations on DWG copies and use `--save-as`. 

## Image/PDF to CAD Draft Generator

`src/neuro_seq_cad/` is an isolated module that converts image/PDF floor plans into editable DXF drafts. It is separated from the existing ZWCAD DWG editing workflow and can run a synthetic demo without external models.

```bash
python -m neuro_seq_cad.app.cli make-sample --out samples/sample_plan.png
python -m neuro_seq_cad.app.cli export-dxf samples/sample_plan.png --out outputs/demo
```

See `docs/21_image_to_cad_pipeline.md` for details.

## Style Context Bridge

`src/hs_style_context` merges drawing grammar samples into `style_context.json`.
`src/neuro_seq_cad_bridge` adapts image-to-CAD results to the current drawing
grammar and creates a dry-run preview insert plan. Existing DWG layers are not
automatically remapped. Real ZWCAD insertion only runs when `--allow-execute`
is provided, and preview plans keep `save: false`.
