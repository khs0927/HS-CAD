# HS-CAD Final Live Runner Test Plan

## Unit tests

- rejects original DWG
- rejects same save_as_target
- rejects unknown alias
- rejects blocked alias
- rejects missing operator_approved
- rejects missing manual_live_flag
- rejects batch commands
- requires before scan
- requires after scan
- requires delta report
- requires audit log

## Local integration tests

- copied DWG scan
- copied DWG SaveAs
- one harmless allowlisted alias candidate
- original hash unchanged
- audit artifact written
- delta artifact written
