# generated/xicad

이 폴더는 XiCAD 카탈로그/매니페스트/부트스트랩 LISP 생성 결과가 저장되는 위치입니다.

주의: `zwai_xicad_bootstrap.lsp`는 사용자의 실제 Windows XiCAD 경로를 기준으로 다시 생성해야 합니다.

```bat
scripts\build_catalog.bat C:\xicad
```

또는:

```bash
python tools/build_xicad_catalog.py --xicad-root "C:/xicad" --out-dir generated/xicad
python tools/install_xicad_support.py --xicad-root "C:/xicad" --out generated/xicad/zwai_xicad_bootstrap.lsp
```
