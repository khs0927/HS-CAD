# HS-CAD Mobile Cloud Development Framework

## Goal

Develop, test, package, and review HS-CAD from an iPhone or iPad without owning a desktop computer.

The framework deliberately separates work into three layers so a paid GPU desktop is only used when a real Windows GUI, ZWCAD, or Rhino is required.

## Recommended architecture

```text
Mobile ChatGPT / GitHub mobile / Safari
                |
                +--> GitHub Codespaces (default interactive development)
                |      - Python 3.11
                |      - Node.js 22
                |      - VS Code in browser
                |      - forwarded web/MCP ports
                |
                +--> GitHub Actions Mobile Remote Control
                |      - doctor
                |      - Python tests
                |      - Windows package build
                |      - mobile CAD tests
                |
                +--> Temporary Windows cloud workstation
                       - only for ZWCAD/Rhino/COM/GPU validation
                       - Azure VM, Vagon, or another licensed Windows GPU PC
                       - Windows App or browser remote desktop
                       - Google Drive for result backup, not program installation
```

## Layer 1: Codespaces is the default desktop replacement

Create a Codespace from the required branch. The repository's `.devcontainer` configuration installs Python 3.11, Node.js 22, GitHub CLI, project dependencies, and mobile CAD dependencies when that app exists on the branch.

Recommended branch choices:

- `feature/mobile-only-chatgpt-cad-app`: mobile CAD/MCP work from PR #127
- `agent/drawing-index-v2`: drawing index V2 work from PR #126
- `feature/mobile-cloud-dev-framework`: this framework

The configuration forwards:

- `3000`: web application
- `5173`: Vite preview
- `8787`: Cloudflare Worker/MCP local development

Codespaces is Linux. It cannot run Windows COM, ZWCAD, Rhino, or interactive Windows installers.

## Layer 2: Mobile Remote Control workflow

Open **Actions -> Mobile Remote Control -> Run workflow** from the GitHub mobile app or browser.

Available tasks:

- `doctor`: run the HS-CAD environment diagnostic on a fresh Windows runner
- `python-tests`: install the project and run the Python test suite
- `windows-package`: build the Windows release package
- `mobile-cad-tests`: type-check, test, and build the mobile CAD app when present
- `all-safe-tests`: run non-destructive safe tests

The workflow uploads logs and outputs as a seven-day artifact. GitHub-hosted runners are temporary and cannot preserve CAD licenses or provide an interactive ZWCAD/Rhino desktop.

## Layer 3: Temporary Windows cloud workstation

Use this layer only for:

- ZWCAD 2025/2026 COM smoke tests
- xiCAD live command validation
- Rhino 8 and Rhino MCP testing
- 3D/OpenGL/GPU validation
- licensed installer and GUI interaction

### Simplest provider choice

For the fewest setup steps, a managed browser cloud computer such as Vagon is simpler than building Azure Virtual Desktop or Microsoft Dev Box infrastructure. Confirm the nearest region, latency, Windows edition, GPU, administrator rights, and CAD license compatibility before paying.

For maximum control and repeatability, use an Azure Windows VM. Start with a CPU VM for setup and 2D tests, then use an NVadsA10 v5 or equivalent GPU VM only when Rhino/3D testing requires it. Configure automatic shutdown and verify that the VM is deallocated after use.

### Bootstrap

After connecting to the Windows cloud PC, open PowerShell and run the repository script:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\bootstrap_cloud_windows.ps1 -InstallGoogleDrive
```

Optional Docker installation:

```powershell
.\scripts\bootstrap_cloud_windows.ps1 -InstallGoogleDrive -InstallDocker
```

The script installs development tools with `winget`, clones or updates HS-CAD, creates `.venv`, installs dependencies, and writes `cloud-doctor.txt`.

ZWCAD and Rhino remain manual because their installers, accounts, licenses, and activation rules are vendor-controlled.

## Google Drive usage

Google Drive is for synchronized inputs, outputs, screenshots, PDFs, DXFs, 3DM files, test evidence, and release backups.

Do not install Windows, ZWCAD, Rhino, Python environments, `node_modules`, Docker data, Git repositories, SQLite working databases, or build caches inside a synchronized Google Drive folder. Work on the cloud PC's local SSD and copy final results to Drive.

Recommended layout:

```text
C:\HS-CAD\                 source, virtual environment, builds
D:\CAD-Test-Workspace\     DWG/DXF/3DM fixtures and temporary copies
G:\My Drive\HS-CAD\        final evidence and backups only
```

## Remote control after a Windows cloud PC exists

The assistant can remotely maintain GitHub branches, workflows, issues, releases, Vercel deployments, databases, and logs through connected tools. Direct control of the Windows GUI requires one of these bridges:

1. A GitHub Actions self-hosted runner installed on the cloud PC.
2. A purpose-built HS-CAD agent/MCP service running on the cloud PC.
3. Manual Windows App access by the user for license prompts and visual verification.

Use a short-lived self-hosted runner registration token. Never commit runner tokens, CAD licenses, passwords, API keys, service-role keys, or `.env` files.

## Simplest operational path

1. Use PR #127 mobile CAD app for new DXF/SVG generation without Windows.
2. Use Codespaces for coding and local web/MCP previews.
3. Trigger Windows packaging and tests with Mobile Remote Control.
4. Rent a Windows GPU cloud PC only for the final ZWCAD/Rhino fixture matrix.
5. Save evidence to GitHub artifacts and Google Drive, then stop/deallocate the cloud PC.

This avoids maintaining Microsoft Dev Box, Azure Virtual Desktop host pools, or an always-running Windows server.
