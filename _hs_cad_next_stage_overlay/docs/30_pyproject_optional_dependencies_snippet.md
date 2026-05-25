# Optional pyproject snippet

기존 `pyproject.toml`에 아래 extra를 검토해서 추가할 수 있습니다.

```toml
[project.optional-dependencies]
cad = ["ezdxf>=1.3.0"]
vision = ["opencv-python-headless>=4.9.0", "pillow>=10.0.0"]
pdf = ["pymupdf>=1.24.0"]
security = ["pip-audit>=2.7.0"]
```

이번 overlay 코드는 위 의존성이 없어도 fallback으로 실행되게 작성되어 있습니다.
