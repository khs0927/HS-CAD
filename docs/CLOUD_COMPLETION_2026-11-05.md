# HS-CAD 클라우드 작업 마무리 보고 (2026-11-05)

브랜치: `claude/cloud-work-completion-upgrade-beuecn` (main 기준, main에는 병합하지 않음)

> **참고:** 이 작업 도중 main에 `khs0927/HS-CAD#161`("chore: deactivate repository")이 병합되었습니다.
> 저장소가 비활성화되었으므로 워크플로는 다시 켜지 않았습니다. 이 브랜치의 CI 변경 사항은
> `.github/workflows-disabled/ci.yml`에만 들어가 있고, 실행되지 않습니다. 다시 활성화하려면 폴더 이름을 되돌리면 됩니다.

## 1. Integrated (통합한 PR/브랜치)

의존 순서(stacked)대로 병합했습니다.

| 순서 | PR | 브랜치 | 내용 | 결과 |
|---|---|---|---|---|
| 1 | khs0927/HS-CAD#146, #147 | `feature/xicad-headless-cores-wal-mtb` → `validation/xicad-headless-zwcad-2026` → `agent/xicad-headless-batches-5-6` | headless core(WAL/MTB/Q1), xiCAD 357개 headless 계약, 197개 bounded CAD 어댑터, `xicad-mcp` 서버 | 충돌 없이 병합. 후속 수정 2건(아래) |
| 2 | khs0927/HS-CAD#154 | `agent/xicad-help-gap-audit` | live-gap backlog 생성기 + 공식 도움말 인덱스 | 깨끗하게 병합 |
| 3 | khs0927/HS-CAD#155 | `agent/xicad-fileops-safety` | 범위가 제한된 파일 트랜잭션 계약 | 깨끗하게 병합 |
| 4 | khs0927/HS-CAD#156 | `agent/xicad-regression-governance` | 레지스트리 수치 검증기 | 병합. baseline 갱신(아래) |
| 5 | khs0927/HS-CAD#124 | `feat/local-semantic-index-framework` | 오프라인·텍스트 독립 CAD 유사도 인덱스 | 깨끗하게 병합 |
| 6 | khs0927/HS-CAD#126 | `agent/drawing-index-v2` | free-only 완전 도면 인덱스 v2 (v0.4.0) | `pyproject.toml` 충돌 해결 (`mcp`와 `tomli`를 모두 유지) |
| 7 | khs0927/HS-CAD#127 | `feature/mobile-only-chatgpt-cad-app` | 모바일 전용 ChatGPT CAD 앱 v0.3 (Cloudflare Worker + MCP) | `.gitignore`, COM 어댑터, 어댑터 테스트 충돌 해결 |

### 통합 중 수정한 사항
- **COM 어댑터 회귀 수정** (`src/adapters/zwcad_com_adapter.py`)
  - #147 버전은 `win32com`/`pythoncom`을 모듈 수준에서 import해서, 기존 main 테스트
    `tests/test_windows_runner_virtualization.py`의 3개 테스트가 실패했습니다. 이 import를 `_load_com()`으로 옮겨
    호출할 때 불러오도록 했고, `start_if_needed=False` 거부 메시지도 복원했습니다.
  - #147은 `scan_modelspace()`가 handle/object_name/layer만 반환하도록 축소했습니다. 그 결과 main의 `scan` CLI가 쓰던
    좌표, 문자, 블록 속성 출력이 빠졌습니다. main의 rich scan(`_entity_to_dict`)을 복원했고, 회귀 테스트도 추가했습니다.
  - #127의 `list_texts()`는 `entity_type` 키(실제 스캔 결과)와 `type` 키를 둘 다 받습니다.
- `src/headless_core/q1_core.py`: `pythoncom` import를 지연시켜 Linux에서도 테스트를 수집할 수 있게 했습니다.
- `catalog/governance/xicad-registry-baseline.json`: #156의 baseline은 `599f41c` 시점 값이었습니다. #147 최신 tip(`4c4123f`)
  기준으로 수치를 갱신했습니다 (CAD mutation alias 190→197, MCP tools 883→894, write/destructive 192→199).
  이 값은 검증기를 실제로 실행해서 확인했습니다.
- 통합한 모듈에 ruff 자동 수정(UP035/I001/UP012)을 적용했습니다.

## 2. Skipped (제외한 항목과 이유)

| 대상 | 이유 |
|---|---|
| khs0927/HS-CAD#1 `stage-23-style-context-bridge` | 현재 main과 공통 조상이 없습니다(main 히스토리 재작성). 고유 파일 213개는 대부분 stage 23–30의 APPLY/PROMPT 문서와 예제입니다. main은 이후 다른 구조로 발전했으므로 superseded로 판단했습니다. |
| khs0927/HS-CAD#4 `spatial-pr4`, #5 `cad-compat-layer-pr5`, #7 `worker-protocol-pr7a` | 역시 공통 조상이 없습니다. main에는 `src/spatial`, `src/workers`, `cad_platforms_cli`, `fusion_matrix_cli`, `layer_audit_cli`, `cross_validate_cli`, `shapely_topology_cli`, `worker_cli`가 이미 있습니다. #7의 base인 #6도 2026-10-08에 닫혔습니다. superseded로 판단했습니다. |
| `agent/xicad-live-geometry-safe` | #147 본문에 따르면 D1 어댑터 시도(#153)는 공식 도움말과 맞지 않아 닫혔습니다(이슈 #149). 의도적으로 제외했습니다. |
| `chore/windows-virtual-validation`, `sync/windows-validation-drawing-index`, `docs/windows-runner-hash-only`, `chore/plugin-orchestrator*`, `chore/orchestrator-evidence-registry`, `feature/mobile-cloud-dev-framework`, `release/*`, `feature/korean-autocomplete-ui` 등 | 열린 PR이 없습니다(닫혔거나 PR이 없음). 대부분 Windows 러너 기록이나 오래된 릴리스 브랜치입니다. 이번 범위에서는 제외했습니다. |

## 3. Upgrades (의존성 업그레이드)

### Python (`pip-audit`: 46건 → 0건)
- `mcp` 1.28.1 → **1.30.0** (CVE-2026-59951, CVE-2026-116684/5/6)
- `Pillow`: Python ≥3.11에서는 **>=13.0,<14** (13.0.0에서 고쳐진 CVE 13건). Pillow 13이 3.10 휠을 내지 않으므로
  Python 3.10에서는 12.3 계열을 유지합니다(환경 마커 사용).
- build-system `setuptools>=84.1` (PYSEC-2026-3447, GHSA-xmj3-9gf7-h52w)
- `requirements.txt`에 `mcp`, `tomli`를 추가해 pyproject와 맞췄습니다.

### Node: `apps/mobile-cad-chatgpt` (`npm audit`: 23건(critical 1) → 0건)
- `@modelcontextprotocol/sdk` 1.29.0 → 1.32.2 (agents의 고정 peer를 `overrides`로 따라가게 함)
- `zod` 4.4.3 → 4.6.7, `vite` 8.1.4 → 8.3.5, `vitest` 4.1.10 → 4.1.12, `happy-dom` 20.10.6 → 21.0.4,
  `wrangler` 4.110.0 → 4.157.0, `@cloudflare/workers-types` 맞춤. 나머지는 `npm audit fix`로 전이 의존성을 정리했습니다.
- `agents`는 0.17.3을 유지합니다. 0.33.0은 optional peer가 매우 많아 npm에서 해석에 실패합니다. 사용하는 API는
  `createMcpHandler` 하나뿐이라 영향은 작습니다.
- 참고: npm 10.9의 arborist `edgesOut` 버그 때문에 일부 단계는 `npx npm@11.6.2`로 실행했습니다. 결과 lockfile은 npm 10 `npm ci`로 검증했습니다.

### CI (`.github/workflows-disabled/ci.yml`, 현재 비활성)
- pytest 다음에 `python scripts/smoke_xicad_mcp_stdio.py`를 실행하도록 추가했습니다.
- `mobile-app` 잡(Node 22): `npm ci` → `npm audit --audit-level=high` → `npm run validate`

## 4. Open-source added (추가한 오픈소스)
새 라이브러리는 추가하지 않았습니다. 통합한 PR이 가져온 것만 있습니다: `mcp`(Python MCP SDK, #147), `tomli`(<3.11 backport, #126),
모바일 앱의 `@modelcontextprotocol/sdk`, `agents`, `@tarikjabiri/dxf`, `dxf-parser`(#127). 문서에 적힌 gap
(ezdxf, shapely, networkx, duckdb)은 이미 main 의존성에 들어 있습니다.

## 5. Verification (검증 명령과 결과)

환경: Linux, Python 3.11.18 (`python3.11 -m venv .venv`, `pip install -e ".[dev]"`), Node 22.23.4 / npm 10.9.9.

| 명령 | 결과 |
|---|---|
| `python -m pytest -q --disable-warnings` (main 기준) | 431 passed, 21 skipped |
| 같은 명령 (통합 후 최종) | **1415 passed, 24 skipped, 0 failed** |
| `pip-audit` | No known vulnerabilities found |
| `python scripts/validate_xicad_registry_truth.py` | `"valid": true` (357 / 197 / 13 / 894 / 199) |
| `python scripts/build_xicad_live_gap_backlog.py --output gap.json` | 160개 non-live 명령 (357−197), workstream별 분류 생성 |
| `python -m src.main --help`, `python -m src.main doctor` | 정상 (Windows 전용 항목은 Linux에서 비활성으로 표시) |
| `npm ci && npm audit` (mobile) | found 0 vulnerabilities |
| `npm run validate` (mobile) | tsc OK, vitest **43/43**, node --test **6/6**, vite build OK, bundle check OK |

### 실제 실행 테스트 (Real run)
1. **xiCAD MCP 서버 (stdio)**: `python scripts/smoke_xicad_mcp_stdio.py .venv/bin/xicad-mcp`
   - `server=HS-CAD xiCAD Headless protocol=2025-11-25 tools=894`
   - `xicad_headless_coverage_summary` → 357/357 계약, production_usable 13
   - `xicad_calculator("(12000-2*200)*(11300-2*200)/1000000")` → `126.440`
   - `__import__('os')` 식 → 거부됨(`unsupported expression element: Call`)
   - 요청 없이 `xicad_execute_live_ct` 호출 → validation error로 거부됨(fail-closed)
2. **도면 인덱스 v2 + 시맨틱 인덱스 (CLI)**: ezdxf로 만든 DXF 3장(한글 라벨 주택, 영문 라벨 주택, 사무실)
   - `python -m src.main corpus-run complete --root run/dxf --workspace run/ws --summary-backend local` → exit 0,
     indexed 3, `network_used: False`
   - `python -m src.main corpus-run query "거실"` → `house_a.dxf` 매칭
   - `python -m src.main semantic-index build/query` → house_a 기준 1위 `house_b.dxf` (score 1.0000, 라벨 언어와 무관),
     2위 `office_c.dxf` (0.9280)
3. **모바일 ChatGPT CAD 앱**: `npm run build` → `npx wrangler dev --local --port 8787`, 이어서 `node scripts/smoke-mcp.mjs http://127.0.0.1:8787/mcp`
   - `"ok": true`, protocol 2025-11-25, 도구 4개(open/render/generate/validate), widget `ui://hscad-mobile/editor-v3.html` (312,925 bytes)
   - HTTP 가드: health 200, malformed 400, oversized 413, unsupported 405, source 404

## 6. Remaining (사용자 Windows CAD 호스트 또는 자격 증명이 필요한 항목)
- **실제 ZWCAD 2025/2026 + xiCAD 라이브 스모크**: `tests/integration/*`(`--run-integration` 또는 `ZWCAD_INTEGRATION_TEST=1`), `scripts/smoke_live_*_drawing1.py`
  등 197개 라이브 어댑터의 실제 도면 검증. #147 본문에도 "Real ZWCAD drawing smoke is still deferred"라고 적혀 있습니다.
- 변경된 COM 어댑터(지연 import, rich scan 복원)를 Windows의 `pywin32` 환경에서 `scan`/`analyze-architecture`로 한 번 확인해야 합니다.
- live-gap backlog 160건은 모두 `manual_review_required`입니다. 공식 도움말 근거와 실제 CAD 검증이 필요합니다(D1은 이슈 #149).
- 모바일 앱 배포(`npm run deploy`)에는 Cloudflare 계정이 필요합니다. ChatGPT 커넥터 등록은 사용자 계정에서 해야 합니다.
- Supabase 요약 백엔드(#126, 선택 기능)에는 `HSCAD_SUPABASE_URL`/`HSCAD_SUPABASE_SERVICE_ROLE_KEY`가 필요합니다.
- main에 실수로 커밋된 `hs_cad.egg-info/`(#161)는 이번에 건드리지 않았습니다. `.gitignore`에는 `*.egg-info/`를 추가했습니다.
- 저장소 비활성화(#161)를 유지할지, 이 브랜치를 PR로 열지는 사용자가 결정해야 합니다.
