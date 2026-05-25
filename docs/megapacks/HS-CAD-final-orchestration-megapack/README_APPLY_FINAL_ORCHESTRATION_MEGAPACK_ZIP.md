# Apply Final Orchestration Megapack ZIP

1. Extract this ZIP into the repository root.
2. Keep validation deferred.
3. Later run:

```powershell
.\scripts\run_final_orchestration_codegen.ps1
```

4. Use:

```text
outputs\CODEX_FINAL_APPLY_PROMPT.md
```

to instruct another local agent to apply all generated ZIPs and build the final bundle.
