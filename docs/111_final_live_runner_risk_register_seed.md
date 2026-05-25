# HS-CAD Final Live Runner Risk Register Seed

| Risk | Severity | Mitigation |
|---|---:|---|
| Original DWG mutation | Critical | copied-DWG only, path inequality, hash audit |
| Destructive command | Critical | allowlist only, deny by default |
| Approval bypass | High | explicit operator_approved and manual_live_flag |
| Batch execution | High | one command only first |
| Missing delta | High | before/after scan and delta report |
| Missing audit | Medium | append-only audit log |
