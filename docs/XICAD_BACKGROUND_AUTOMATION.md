# XiCAD Background Architectural Automation

HS-CAD can discover all aliases in an installed XiCAD shortcut file, compile architectural elements into command prompt scripts, queue work persistently, and execute approved jobs through one monitored ZWCAD COM worker.

## What is automated

- All aliases found in `XiCAD/Lisp/xiShortkey_origin.key` are registered in the catalog.
- Walls, doors, windows, columns, beams, stairs, elevators, parking, insulation, annotations, and custom elements can be represented in one architectural design JSON.
- Verified prompt contracts convert element parameters into exact XiCAD command-line answers.
- Jobs survive program restarts in a SQLite WAL queue.
- One COM STA worker executes jobs sequentially and waits for `CMDACTIVE=0` and an empty `CMDNAMES` value.
- Every job uses a separate working DWG, recovery copy, optional per-step checkpoints, timeout, cooperative cancellation, entity-count verification, and save-after-step policy.
- A SHA-256 approval token binds permission to the exact source, output, XiCAD root, aliases, arguments, and safety options.

## Important meaning of “all commands”

Every discovered alias can be cataloged, queued, audited, and given a reusable prompt contract. XiCAD commands that require mouse clicks or command-line questions cannot safely run unattended until their exact prompt sequence has been observed on the installed XiCAD/ZWCAD version.

HS-CAD therefore uses this policy:

1. Unknown alias: reject.
2. Known interactive alias without arguments or verified contract: block.
3. Verified prompt contract: compile and permit background execution after approval.
4. High-risk alias: require a separate `allow_high_risk=true` flag.
5. Original DWG: never modify; copy to `working_dwg` first.

This is a default-deny architecture, not a claim that undocumented XiCAD input contracts are known.

## 1. Inventory the installed XiCAD commands

```powershell
HS-CAD.exe xicad-bg-catalog `
  --xicad-root "C:\XiCAD" `
  --out "C:\HS-CAD\xicad-catalog.json"
```

The output includes alias, description, category, risk, whether interaction is expected, and whether a verified unattended recipe is available.

Create one protected template for every discovered command:

```powershell
HS-CAD.exe xicad-contract-bootstrap-all `
  --xicad-root "C:\XiCAD" `
  --out-dir config\xicad_contracts
```

Existing contract files are preserved unless `--overwrite` is explicitly supplied.

## 2. Record each interactive command contract

Use the existing observation wizard on a disposable DWG:

```powershell
HS-CAD.exe xicad-contract-wizard --alias WAL --out-dir outputs\xicad_contracts
```

Then edit the corresponding reusable contract file. A single template can also be created with:

```powershell
HS-CAD.exe xicad-contract-template `
  --alias WAL `
  --out config\xicad_contracts\WAL.json
```

Replace `argument_templates` with the observed prompt order. Example only:

```json
{
  "alias": "WAL",
  "argument_templates": ["{start}", "{end}", "{thickness}"],
  "verified": true,
  "zwcad_version": "2026",
  "xicad_version": "observed version",
  "notes": "Validated on a disposable drawing; UNDO restored the initial state."
}
```

Do not set `verified=true` based only on the example. Confirm the installed version manually first.

## 3. Describe the architectural drawing

Start with:

`examples/xicad_background/architectural_design.example.json`

Each element has a semantic kind, XiCAD alias, and parameters used by the prompt contract.

## 4. Compile architecture into a workflow

```powershell
HS-CAD.exe xicad-arch-compile `
  --design examples\xicad_background\architectural_design.example.json `
  --contracts config\xicad_contracts `
  --out outputs\xicad_background\compiled_workflow.json
```

Compilation fails when a required contract is missing or unverified.

## 5. Validate in dry-run

```powershell
HS-CAD.exe xicad-bg-validate `
  --workflow outputs\xicad_background\compiled_workflow.json
```

The validator checks source DWG, separate output path, XiCAD loader, alias membership, prompt contracts, risk flags, and approval state.

## 6. Approve the exact live workflow

The safest path writes live mode and the approval token in one explicit operation:

```powershell
HS-CAD.exe xicad-bg-approve `
  --workflow outputs\xicad_background\compiled_workflow.json `
  --confirm LIVE-XICAD
```

The lower-level token command remains available for review-only workflows:

```powershell
HS-CAD.exe xicad-bg-token `
  --workflow outputs\xicad_background\compiled_workflow.json
```

Any later change to coordinates, aliases, arguments, paths, or options invalidates the token.

## 7. Submit and inspect the queue

```powershell
HS-CAD.exe xicad-bg-submit `
  --workflow outputs\xicad_background\compiled_workflow.json `
  --db "$env:LOCALAPPDATA\HS-CAD\xicad-jobs.sqlite3"

HS-CAD.exe xicad-bg-status `
  --db "$env:LOCALAPPDATA\HS-CAD\xicad-jobs.sqlite3"
```

Cancel a pending, blocked, or running job:

```powershell
HS-CAD.exe xicad-bg-cancel `
  --job-id <job-id> `
  --db "$env:LOCALAPPDATA\HS-CAD\xicad-jobs.sqlite3"
```

A running job moves to `cancelling`; the COM idle monitor sends a cancel signal and stores a final `cancelled` result.

## 8. Install the background worker

Run PowerShell as the same Windows user who runs ZWCAD:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_xicad_background_worker.ps1 `
  -Executable "$env:LOCALAPPDATA\Programs\HS-CAD\HS-CAD.exe" `
  -ZwcadVersion 2026
```

The scheduled task starts at interactive logon and restarts after failure. COM automation is intentionally tied to an interactive user session because desktop CAD applications are not reliable Windows services in Session 0.

Uninstall:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_xicad_background_worker.ps1 -Uninstall
```

## Runtime sequence

```text
Architectural JSON
  -> verified contract compiler
  -> immutable workflow + approval token
  -> SQLite persistent queue
  -> one COM STA worker
  -> copy source DWG
  -> load XiCAD
  -> command + exact prompt answers
  -> CMDACTIVE/CMDNAMES idle wait
  -> scan and verify
  -> save + checkpoint
  -> final result in SQLite
```

## Recovery

- The original DWG is never opened for mutation.
- A recovery copy is created before XiCAD execution.
- Each requested checkpoint copies the saved working DWG after the step.
- A timed-out or cancelled command receives two cancel control characters.
- An abandoned `running` job is returned to `pending` when the single worker starts again.
- An abandoned `cancelling` job is finalized as `cancelled` on restart.
- Failed jobs preserve the working/recovery/checkpoint files for review.

## Recommended rollout

1. Use a disposable drawing and one alias.
2. Record and validate the prompt contract.
3. Run a one-step dry-run workflow.
4. Run a one-step approved workflow on a copy.
5. Compare entity count, layers, blocks, texts, and visual output.
6. Add the next alias.
7. Only after the core wall/opening commands are verified, enable complete floor-plan workflows.
