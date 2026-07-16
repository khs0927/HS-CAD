# HS-CAD Plugin Orchestrator

## Purpose

HS-CAD validation and release work must continue even when GitHub Actions is unavailable. The orchestrator separates planning, source control, validation, deployment, data, and observability so that one provider failure does not block every lane.

## Single validation contract

Every runner executes the same command and produces the same JSON evidence:

```powershell
python scripts/run_plugin_orchestrator.py --profile auto
```

Default evidence:

```text
outputs/orchestrator/latest.json
```

Profiles:

| Profile | Scope |
|---|---|
| `core` | compile, portable pytest, Ruff, wheel build |
| `drawing-index` | free-only policy, drawing-index contract and tests |
| `semantic` | semantic-index tests discovered by filename |
| `windows-cad` | real Windows/ZWCAD fixture matrix |
| `auto` | detects modules present in the current branch |

The runner never uses `shell=True`, does not print environment-variable values, redacts the private fixture root from the JSON command record, and fails closed on a non-zero command, timeout, or process error.

## Container execution

```powershell
docker build -f Dockerfile.orchestrator -t hscad-orchestrator .
docker run --rm hscad-orchestrator
```

This is the preferred Linux validation path for Manufact or any other authenticated private-repository builder.

## Orchestration lanes

### Control plane

- **Linear**: priority, dependencies, acceptance criteria, blockers and completion evidence.
- **GitHub**: private source, branches, PRs, reviews and releases. GitHub Actions is not part of the required flow.

### Validation plane

1. Local or hosted container executes `run_plugin_orchestrator.py`.
2. Manufact is the preferred connected private-repository runner after its GitHub App is granted access.
3. Windows/ZWCAD acceptance runs only on a licensed Windows host with private fixtures.
4. Netlify and Vercel validate web/PWA/MCP surfaces, not desktop COM behavior.

### Documentation plane

- **Context7** verifies current official APIs when a dependency integration changes.
- The result is referenced in the relevant PR or Linear issue.

### Data plane

- Local SQLite remains authoritative for drawing content and search.
- Supabase may receive redacted aggregate statistics only.
- Neon is optional for server-side SQL validation and is never a local-runtime requirement.

### Observability plane

- Alpic monitors deployed MCP traffic.
- Manufact provides build and runtime logs.
- Deployment health is evidence, but it does not replace test or Windows fixture evidence.

## PR release gates

### PR #126 — Drawing Index V2

Required:

1. `core` and `drawing-index` profiles pass.
2. Supabase privacy guards pass.
3. Windows/ZWCAD fixture matrix passes on at least five representative drawings.
4. Native and fallback evidence is compared.
5. Original drawings remain unchanged.

### PR #124 — Semantic Index

Required:

1. PR #126 is merged first.
2. `core` and `semantic` profiles pass.
3. At least 20 real FileizedDrawingRecord files are indexed.
4. Top-5 results are manually reviewed.
5. Precision@5, Recall@5 and Hit@5 are stored as JSON evidence.

### PR #127 — Mobile ChatGPT CAD App

Required:

1. Public health and MCP protocol checks pass.
2. ChatGPT custom app registration succeeds.
3. iPhone/iPad widget acceptance succeeds.
4. SVG and DXF export are manually checked.
5. Deployment logs show no release-blocking runtime errors.

## Failure routing

| Failure | Route |
|---|---|
| GitHub Actions unavailable | Ignore Actions; use orchestrator container |
| Manufact cannot read private repo | GitHub App access gate; continue static review and local/container preparation |
| Context7 authentication unavailable | Record documentation gate as blocked; do not claim API verification |
| Netlify/Vercel unavailable | Keep local PWA build and public Worker health evidence |
| Supabase unavailable | Continue local SQLite; remote summary is optional |
| No Windows/ZWCAD host | Keep PR Draft; do not claim production acceptance |

## Release order

1. Merge this orchestrator foundation.
2. Validate and merge Drawing Index V2.
3. Rebase, evaluate and merge Semantic Index.
4. Complete mobile app registration and merge the ChatGPT app.
