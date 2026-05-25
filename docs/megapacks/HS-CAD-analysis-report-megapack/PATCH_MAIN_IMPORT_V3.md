# PATCH — Register CLI shortcut v3

Add this import in `src/main.py` near other CLI imports:

```python
import src.app.analysis_shortcut_cli_v3  # noqa: F401,E402
```

Keep validation TODO until local integration.
