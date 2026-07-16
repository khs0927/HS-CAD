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
| `core` | Python compile, portable pytest, Ruff, wheel build |
| `drawing-index` | free-only policy, drawing-index contract, corpus/privacy/fallback tests |
| `semantic` | semantic-index tests discovered by filename |
| `mobile` | Node version, locked install, tests/build/Worker dry-run, license and secret scans |
| `windows-cad` | real Windows/ZWCAD fixture matrix |
| `auto` | detects modules and apps present in the current branch |

Profiles can be combined by repeating `--profile`, except that `auto` cannot be combined with explicit profiles.

The runner never uses `shell=True`, does not print environment-variable values, redacts repository/home/private-fixture paths, restricts per-check working directories to the repository tree, and fails closed on a non-zero command, timeout, process error, platform mismatch, path escape, or an explicitly requested profile with no runnable checks.

By default, evidence contains only SHA-256 hashes of stdout/stderr. Sanitized log tails are included only when `--include-logs` is explicitly supplied. This prevents drawing names, customer paths, extracted text, and package-manager output from being copied into an external control plane by default.

## Hybrid container execution

The shared image contains Python 3.11 and Node.js 22.18 so the same runner validates the Python desktop/index code and the mobile ChatGPT app.

```powershell
docker build -f Dockerfile.orchestrator -t hscad-orchestrator .
docker run --rm hscad-orchestrator
```

`Dockerfile.orchestrator.dockerignore` excludes Git metadata, Python and Node virtual/dependency folders, Wrangler output, environment files, build/output folders, private fixture folders, and DWG/DXF files from the build context. Committed synthetic test fixtures under `tests/fixtures/` remain available. A hosted runner receives source code and tests, not local office drawing data.

This is the preferred Linux validation path for Manufact or any other authenticated private-repository builder.

## Direct profile commands

Drawing Index V2:

```powershell
python scripts/run_plugin_orchestrator.py `
  --profile core `
  --profile drawing-index `
  --continue-on-error
```

Semantic Index:

```powershell
python scripts/run_plugin_orchestrator.py `
  --profile core `
  --profile semantic `
  --continue-on-error
```

Mobile ChatGPT CAD App:

```powershell
python scripts/run_plugin_orchestrator.py `
  --profile mobile `
  --continue-on-error
```

The mobile profile runs, in order:

1. Node.js 22.18+ guard;
2. `npm ci --no-audit --no-fund`;
3. `npm run validate:ci`;
4. `npm run security:local`.

`validate:ci` includes TypeScript checking, unit tests, bootstrap/deployment-script tests, Vite build, bundle inspection, and Cloudflare Worker dry-run.

Windows/ZWCAD acceptance:

```powershell
python scripts/run_plugin_orchestrator.py `
  --profile windows-cad `
  --fixture-root "D:\PRIVATE-DRAWING-FIXTURES"
```

## Orchestration lanes

### Control plane

- **Linear**: priority, dependencies, acceptance criteria, blockers and completion evidence.
- **GitHub**: private source, branches, PRs, reviews and releases. GitHub Actions is not part of the required flow.

### Validation plane

1. Local or hosted hybrid container executes `run_plugin_orchestrator.py`.
2. Manufact is the preferred connected private-repository runner after repository access is granted.
3. Windows/ZWCAD acceptance runs only on a licensed Windows host with private fixtures.
4. Cloudflare validates the production MCP/Widget runtime.
5. Netlify and Vercel validate web/PWA/API surfaces, not desktop COM behavior.

### Documentation plane

- **Context7** verifies current official APIs when a dependency integration changes.
- The result is referenced in the relevant PR or Linear issue.

### Data plane

- Local SQLite remains authoritative for drawing content and search.
- Supabase may receive redacted aggregate statistics only.
- Neon is optional for server-side SQL validation and is never a local-runtime requirement.

### Observability plane

- Alpic monitors deployed MCP traffic after a project is connected.
- Manufact provides build and runtime logs after repository access is connected.
- Vercel provides web runtime logs where Vercel is the selected deployment surface.
- Deployment health is evidence, but it does not replace tests or Windows fixture evidence.

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

1. `mobile` profile passes.
2. Public health and MCP protocol checks pass.
3. ChatGPT custom app registration succeeds.
4. iPhone/iPad widget acceptance succeeds.
5. SVG and DXF exports are manually checked.
6. Deployment logs show no release-blocking runtime errors.

## Failure routing

| Failure | Route |
|---|---|
| GitHub Actions unavailable | Ignore Actions; use orchestrator container |
| Manufact cannot read private repo | Repository-access gate; continue static review and local/container preparation |
| Context7 authentication unavailable | Record documentation gate as blocked; do not claim API verification |
| Netlify/Vercel unavailable | Keep local mobile profile and public Worker health evidence |
| Supabase unavailable | Continue local SQLite; remote summary is optional |
| No Windows/ZWCAD host | Keep PR #126 Draft; do not claim production acceptance |
| ChatGPT app not registered | Keep PR #127 Draft; public Worker health is not mobile acceptance |

## Release order

1. Merge the orchestrator v1.1 profile expansion.
2. Validate and merge Drawing Index V2.
3. Rebase, evaluate and merge Semantic Index.
4. Complete mobile app registration and merge the ChatGPT app.
