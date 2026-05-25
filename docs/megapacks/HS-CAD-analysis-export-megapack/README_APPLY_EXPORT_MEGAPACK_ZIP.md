# Apply Export Megapack ZIP

1. Checkout your local final branch.

```powershell
git switch local-megapack-final
```

2. Extract this ZIP into the repository root.

3. Apply manual patches:

```text
PATCH_WORKER_MANIFEST_ANALYSIS_EXPORT.md
PATCH_MAIN_IMPORT_V2.md
```

4. Do not validate yet if you are continuing code generation.

5. Later validation is preserved in:

```text
docs/VALIDATION_TODO_EXPORT_MEGAPACK.md
```

6. Later package command:

```powershell
Compress-Archive -Path config,docs,src,scripts -DestinationPath outputs\HS-CAD-final-megapack-code.zip -Force
```
