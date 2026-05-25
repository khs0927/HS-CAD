# HS-CAD Final Live Runner Safety Spec Seed

## Status

Seed only. Do not implement runner in this PR.

## Required safety conditions

1. copied DWG only
2. original and copy paths must differ
3. save_as_target must differ from original and copy
4. alias must be allowlisted
5. blocked aliases always fail
6. unknown aliases always fail
7. operator_approved must be explicit true
8. manual_live_flag must be explicit true
9. first implementation allows one harmless command only
10. before scan required
11. after scan required
12. delta report required
13. audit log required
14. original hash before/after must match
15. default disabled and fail-closed

## First implementation PR must not include

- batch execution
- original DWG mutation
- automatic approval
- unknown alias
- destructive alias
