# PATCH — Register Pipeline CLI

Add this import in `src/main.py` near other CLI imports:

```python
import src.app.analysis_pipeline_cli  # noqa: F401,E402
```

Keep validation TODO until local integration.
