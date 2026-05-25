# HS-CAD Final Live Runner Risk Register

| Risk | Severity | Mitigation |
|---|---:|---|
| Original DWG mutation | Critical | copied-DWG only, path inequality, before/after hash |
| Destructive command | Critical | allowlist only, deny by default |
| Unknown alias execution | Critical | fail closed |
| Approval bypass | High | explicit operator_approved and manual_live_flag |
| Batch execution | High | first runner limited to one command |
| No delta visibility | High | before/after scan and delta required |
| No audit trail | Medium | append-only audit required |
