# Apply Manual Copy-only Interface

This branch adds a review-only operator interface after the preflight guard.

## Apply locally

Use the ZIP package from ChatGPT if you need the full local patch, including tests and report templates.

## Register CLI locally

Add this import to `src/main.py` when applying the full ZIP locally:

```python
import src.app.final_live_runner_manual_copy_interface_cli  # noqa: F401,E402
```

## Safety

This package is dry-run only. It produces review and audit artifacts and does not perform CAD operations.
