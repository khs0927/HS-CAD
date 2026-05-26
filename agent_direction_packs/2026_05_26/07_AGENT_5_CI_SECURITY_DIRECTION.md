# 07. Agent 5 – CI / Security Direction

## 역할

Agent 5는 GitHub Actions와 보안 가드를 구현한다.

## 현재 상태

- 현재 main에는 `.github/workflows/corpus-foundation.yml`만 확인됨.
- CI/security 계획 문서는 존재한다.
- Quality Gate workflow는 아직 main에 확인되지 않는다.

## 다음 순서

1. PR #111 병합 대기.
2. Agent 2가 `quality_gate_scan.py`를 만들면 CI에 연결한다.
3. GitHub Actions workflow를 별도 PR로 추가한다.

## workflow 요구사항

파일 후보:

```text
.github/workflows/quality-gate.yml
```

필수 job:

- Python 3.11 setup
- requirements 설치
- `python scripts/quality_gate_scan.py --strict`
- `python -X utf8 -m compileall -q src tests scripts`
- `python -X utf8 -m pytest -q`
- artifact/binary guard
- high-risk file guard

## 금지

- Linux GitHub runner에서 ZWCAD/AutoCAD/PyRx/ODA 설치 요구
- Windows CAD live test
- SendCommand / SaveAs / DXFOUT 실행
- release artifact publishing
- secrets 출력

## GitHub workflow 권한 주의

workflow file push는 token에 workflow scope가 필요할 수 있다. 권한 부족 시 무리하지 말고 `workflow scope required`로 보고한다.
