# Patch `src/main.py`

Add these imports after the existing app CLI imports so the shortcut commands are registered.

```python
import src.app.worker_cli  # noqa: F401,E402
import src.app.analysis_shortcut_cli  # noqa: F401,E402
```

Recommended final area:

```python
import src.app.spatial_cli  # noqa: F401,E402
import src.app.worker_cli  # noqa: F401,E402
import src.app.analysis_shortcut_cli  # noqa: F401,E402
```

This adds:

```text
hscad-analysis-run-all
hscad-analysis-summary
hscad-analysis-dashboard
hscad-analysis-package
```
