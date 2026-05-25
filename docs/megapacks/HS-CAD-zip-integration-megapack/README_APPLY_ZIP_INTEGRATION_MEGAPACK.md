# Apply ZIP Integration Megapack

1. Extract this ZIP into the repository root.
2. Put previously generated ZIPs in the same folder or provide `-ZipDir`.
3. Run:

```powershell
.\scripts\run_codegen_only_finalize.ps1 -ZipDir . -RepoRoot . -Out outputs\HS-CAD-final-codegen-bundle.zip
```

4. Do not validate yet if continuing code generation.
5. Later validation is documented in:

```text
docs/VALIDATION_TODO_ZIP_INTEGRATION.md
```
