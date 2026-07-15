# HS-CAD Free-Only Mobile Development Framework

## Final conclusion

A desktop computer is not required for most HS-CAD development, testing, packaging, and mobile CAD work.

The permanent zero-cost path is:

```text
Mobile ChatGPT + GitHub connector
        |
        +--> github.dev browser editor (unlimited editor, no compute)
        |
        +--> GitHub Actions included quota (manual runs only)
        |      - Linux tests by default
        |      - Windows doctor/package only when necessary
        |
        +--> GitHub Codespaces included quota (optional interactive terminal)
        |
        +--> Cloudflare Workers Free (mobile CAD/MCP deployment)
        |
        +--> Local SQLite by default
               or one free Neon/Supabase project when remote data is required
```

A permanently free interactive Windows GPU desktop capable of running Rhino and ZWCAD is not available from the reviewed mainstream services. Microsoft Dev Box, Windows 365, Azure GPU VMs, Azure Virtual Desktop, AWS WorkSpaces, Vagon, and similar services are excluded from the free-only architecture.

## What can be completed for free

- Repository inspection and code changes through ChatGPT and the GitHub connector
- Lightweight browser editing through `github.dev`
- Python and TypeScript development through the monthly Codespaces allowance
- Linux and Windows CI within the monthly GitHub Actions allowance
- Windows EXE and installer packaging on a temporary GitHub-hosted Windows runner
- Mobile CAD SVG/DXF generation from PR #127 without ZWCAD
- MCP and mobile web deployment on Cloudflare Workers Free
- Local SQLite indexing and audit history
- Small remote database workloads on Neon Free or Supabase Free
- Final-result backup within the user's existing Google Drive free storage allowance

## What cannot be completed permanently for free

- Interactive ZWCAD or Rhino GUI sessions in a cloud Windows desktop
- GPU/OpenGL validation using a permanent cloud GPU workstation
- Live ZWCAD COM automation against a licensed installed application
- Live xiCAD command execution
- Rhino plug-in and Rhino MCP validation against a licensed Rhino installation

GitHub-hosted Windows runners are temporary, non-interactive machines. They can compile, test, and package Windows software, but they cannot be used as an RDP desktop and cannot preserve CAD licenses between runs.

## Layer 1: github.dev is the default editor

Use `github.dev` for quick edits, reviews, Markdown, YAML, and small code changes. It runs as a browser editor and does not consume Codespaces compute.

For this project, most code generation and repository changes can also be completed remotely by ChatGPT through the connected GitHub tools, so the mobile browser is mainly needed for review and approval.

## Layer 2: Codespaces is optional, not the default

Use Codespaces only when an interactive terminal or live web preview is necessary.

The repository `.devcontainer` requests the smallest practical machine:

- 2 CPU cores
- 8 GB memory
- Python 3.11
- Node.js 22
- GitHub CLI

The configuration forwards:

- `3000`: web application
- `5173`: Vite preview
- `8787`: Cloudflare Worker/MCP local development

Free-quota rules:

1. Use a 2-core codespace.
2. Stop the codespace immediately after each session.
3. Delete unused codespaces instead of retaining them.
4. Do not enable prebuilds.
5. Keep large DWG, PDF, OCR model, and build-output files outside the codespace.
6. Keep the GitHub billing budget at zero or do not register a payment method if accidental billing must be impossible.

Codespaces is Linux and cannot run Windows COM, ZWCAD, Rhino, or Windows installers interactively.

## Layer 3: Mobile Remote Control workflow

Open **Actions -> Mobile Remote Control -> Run workflow** from the GitHub mobile app or browser.

The workflow is manual-only so commits and pull requests do not consume minutes automatically.

Tasks:

- `doctor-linux`: cheapest default environment check
- `python-tests-linux`: Python test suite on Linux
- `mobile-cad-tests-linux`: TypeScript mobile CAD checks and build
- `windows-doctor`: Windows-specific diagnostic only when required
- `windows-package`: Windows EXE and installer build only when required

Cost-control behavior:

- Linux is used for routine work.
- Windows runners are used only for Windows-specific validation.
- Every job has a 30-minute timeout.
- Result artifacts are retained for one day.
- Concurrent duplicate jobs are canceled.
- No scheduled or pull-request-triggered runs are configured.

For a private repository, these jobs consume the account's included monthly Actions allowance. With no valid payment method, GitHub blocks further usage after the allowance is exhausted rather than continuing as paid usage.

## Deployment

Use the PR #127 Cloudflare Workers deployment as the default mobile CAD/MCP hosting target.

Cloudflare Workers Free is preferred over Vercel Hobby for this project because Vercel Hobby is restricted to non-commercial personal use. The HS-CAD repository is private and may support professional work, so Vercel Hobby should not be treated as the default zero-cost production host.

Free deployment rules:

- Keep the Worker stateless where possible.
- Keep CPU work below the free invocation limit.
- Do not attach paid Workers services.
- Do not switch the account to the Workers Paid plan.
- Use Cloudflare D1 Free only if a database is necessary; otherwise retain local SQLite or the existing free database.

## Database choice

Use only one remote database to avoid duplicated maintenance.

Recommended order:

1. Local SQLite for drawing indexes, local run history, and sensitive CAD metadata.
2. Neon Free for a small always-available development database with scale-to-zero behavior.
3. Supabase Free only when Supabase Auth, Storage, or Realtime is specifically required.

Do not provision paid branches, paid compute, point-in-time recovery, custom domains, or usage-based add-ons.

## Google Drive

Google Drive is backup storage only. It is not a cloud computer and cannot host Windows applications.

Store only compact final outputs:

- PDF exports
- compressed DXF/3DM test files
- screenshots
- test reports
- release installers
- ZIP archives

Do not store live `.venv`, `node_modules`, `.git`, Docker data, SQLite working databases, build caches, or synchronized CAD temporary files.

## Rhino and ZWCAD validation policy

Until access to a real licensed Windows CAD computer is available, PRs that require live ZWCAD/Rhino verification must remain Draft and clearly state that limitation.

Use the following substitutes in the free path:

- `ezdxf` for DXF structure and geometry validation
- SVG/PDF rendering for visual review
- synthetic fixture drawings
- unit and contract tests for COM adapter methods
- GitHub-hosted Windows runners for imports, packaging, and non-interactive checks
- PR #127 browser CAD engine for mobile-generated drawing sets

These substitutes validate code and file generation but do not prove that a real ZWCAD/Rhino installation behaves correctly.

## Operational sequence

1. ChatGPT modifies the repository through GitHub tools.
2. Review files in the GitHub mobile app or `github.dev`.
3. Run `doctor-linux` or focused Linux tests manually.
4. Run Windows jobs only before packaging or merging Windows-specific changes.
5. Use Codespaces only for terminal-based debugging that cannot be done through Actions.
6. Deploy the mobile CAD/MCP app to Cloudflare Workers Free.
7. Store only final compact evidence in Google Drive.
8. Leave ZWCAD/Rhino-dependent PRs in Draft until a licensed physical or sponsored Windows machine becomes available.

## Zero-cost safety checklist

- GitHub metered-product budget: zero
- No paid GitHub larger runners
- No Codespaces prebuilds
- 2-core Codespaces only
- Manual Actions only
- One-day artifact retention
- Cloudflare Workers Free plan only
- No Azure, AWS WorkSpaces, Dev Box, Windows 365, Vagon, or paid GPU VM
- No Fal paid inference in required runtime
- No Hugging Face paid Jobs or Endpoints in required runtime
- Local SQLite by default
- Neon or Supabase Free only when necessary
- No paid domain required; use provider subdomains
