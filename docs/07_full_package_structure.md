# Full Package Structure

이 패키지는 두 부분으로 구성됩니다.

```text
zwcad-ai-modifier/      # ZWCAD AI Modifier 소스 코드
vendor/xicad/           # 업로드된 XiCAD 원본 관련 파일 전체
```

## XiCAD 원본 관련 주요 폴더

```text
vendor/xicad/_ZWCad/    # ZWCAD용 CUIX, PGP, LIN, PAT, ZRX, zwcad.lsp
vendor/xicad/Lisp/      # XiCAD 본체 LISP/FAS/ZELX 및 단축키 정의
vendor/xicad/Lib/       # 건축 DWG 블록 라이브러리
vendor/xicad/xiLib/     # 문창, 구조, 위생, 벽천장 등 XiCAD 라이브러리
vendor/xicad/DialogBox/ # XiCAD 대화상자 리소스
```

## AI Modifier 연동 핵심 파일

```text
src/adapters/xicad_adapter.py              # ZWCAD COM 기반 XiCAD 로드/명령 큐잉
src/integrations/xicad_paths.py            # XiCAD 폴더 구조 자동 감지
src/integrations/xicad_manifest.py         # XiCAD 파일 매니페스트 생성
src/integrations/xicad_command_catalog.py  # xiShortkey_origin.key 파싱
src/integrations/xicad_workflows.py        # AI 작업명 → XiCAD 명령 alias 매핑
tools/build_xicad_catalog.py               # 명령 카탈로그/파일 매니페스트 생성
tools/install_xicad_support.py             # ZWCAD용 XiCAD bootstrap LISP 생성
```

## 권장 실행 순서

1. Windows PC에 ZWCAD와 Python을 설치합니다.
2. 이 패키지를 예: `C:\zwcad-ai-modifier-xicad-full`에 압축 해제합니다.
3. XiCAD 실제 경로를 정합니다. 이 패키지 포함본을 쓰면 `C:\zwcad-ai-modifier-xicad-full\vendor\xicad`입니다.
4. 카탈로그와 bootstrap을 재생성합니다.

```bat
cd C:\zwcad-ai-modifier-xicad-full\zwcad-ai-modifier
scripts\build_catalog.bat C:\zwcad-ai-modifier-xicad-full\vendor\xicad
```

5. ZWCAD에서 `generated\xicad\zwai_xicad_bootstrap.lsp`를 APPLOAD 또는 `(load "...")`로 로드합니다.
6. CLI로 XiCAD 명령을 호출합니다.

```bat
python -m src.main run-xicad --dwg "C:\cad\sample.dwg" --xicad-root "C:\zwcad-ai-modifier-xicad-full\vendor\xicad" --load-first --alias WAL
```
