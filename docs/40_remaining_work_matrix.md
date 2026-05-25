# HS-CAD Remaining Work Matrix

| Area | Current state | Remote-safe next action | Local-only action |
|---|---|---|---|
| Main review pipeline | PR #66 | Merge after CI | Re-run full test suite |
| Evidence schema bridge | PR #68 | Retarget after PR #66 | Inspect real output folders |
| Review output quality | PR #70 | Keep as planning PR | Apply v7 package and validate |
| Megapack finalization | PR #71 | Merge after stack updates | None |
| Golden artifacts | Pending | Define schema and docs | Generate from real outputs |
| Report/evidence IDs | Partial | Add design docs | Validate report snapshots |
| Domain rules | Baseline only | Add plan-only specs | Validate with project samples |
| PDF/image adapters | Boundary only | Add optional adapter plan | Test optional deps locally |
| Windows boundary checks | Pending | Add non-mutating test plan | Run on Windows worktree |
