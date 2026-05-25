# PATCH — Register CLI shortcut v2

After applying this ZIP, add this import in `src/main.py` near the other CLI imports:

```python
import src.app.analysis_shortcut_cli_v2  # noqa: F401,E402
```

Keep validation TODO until local integration.
