# Reframed Framework

The project is now organized around five layers:

1. **Command Layer**: CLI and future UI accept only validated JSON commands.
2. **Safety Layer**: dry-run first, backup before mutation, no original overwrite without explicit save-as.
3. **CAD Adapter Layer**: ZWCAD COM is the executable fallback; PyRx remains the future high-performance adapter.
4. **Architecture Intelligence Layer**: static drawing analysis, planned actions, reports and XiCAD preparation.
5. **XiCAD Bridge Layer**: XiCAD is an interactive architecture command engine, invoked only through safe catalog aliases.

Recommended development flow:

```text
DWG scan -> architecture audit -> dry-run command plan -> safe execute on copied DWG -> post-scan diff -> report
```

The next milestone is to gather real `objects.json` samples from Windows + ZWCAD and use them to harden entity parsing and block replacement.
