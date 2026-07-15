[CmdletBinding()]
param(
    [string]$RepoUrl = "https://github.com/khs0927/HS-CAD.git",
    [string]$Workspace = "C:\HS-CAD",
    [switch]$InstallDocker,
    [switch]$InstallGoogleDrive,
    [switch]$SkipClone
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Assert-Windows {
    if (-not $IsWindows) {
        throw "This bootstrap script must run on Windows 10/11 or Windows Server."
    }
}

function Install-WingetPackage {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $existing = winget list --id $Id --exact --accept-source-agreements 2>$null
    if ($LASTEXITCODE -eq 0 -and $existing -match [regex]::Escape($Id)) {
        Write-Host "$Name is already installed."
        return
    }

    Write-Host "Installing $Name..."
    winget install --id $Id --exact --silent --accept-package-agreements --accept-source-agreements
}

Assert-Windows

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "winget is required. Update App Installer from Microsoft Store, then rerun this script."
}

Install-WingetPackage -Id "Git.Git" -Name "Git"
Install-WingetPackage -Id "GitHub.cli" -Name "GitHub CLI"
Install-WingetPackage -Id "Microsoft.VisualStudioCode" -Name "Visual Studio Code"
Install-WingetPackage -Id "Python.Python.3.11" -Name "Python 3.11"
Install-WingetPackage -Id "OpenJS.NodeJS.LTS" -Name "Node.js LTS"
Install-WingetPackage -Id "Microsoft.PowerShell" -Name "PowerShell 7"

if ($InstallDocker) {
    Install-WingetPackage -Id "Docker.DockerDesktop" -Name "Docker Desktop"
}

if ($InstallGoogleDrive) {
    Install-WingetPackage -Id "Google.GoogleDrive" -Name "Google Drive for desktop"
}

$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machinePath;$userPath"

if (-not $SkipClone) {
    if (Test-Path (Join-Path $Workspace ".git")) {
        Write-Host "Updating existing repository at $Workspace..."
        git -C $Workspace fetch --all --prune
    } elseif (Test-Path $Workspace) {
        throw "$Workspace exists but is not a Git repository. Choose another -Workspace path."
    } else {
        git clone $RepoUrl $Workspace
    }
}

if (-not (Test-Path $Workspace)) {
    New-Item -ItemType Directory -Force -Path $Workspace | Out-Null
}

Set-Location $Workspace

$python = Get-Command py -ErrorAction SilentlyContinue
if ($python) {
    py -3.11 -m venv .venv
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip wheel
    & .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
    & .\.venv\Scripts\python.exe -m src.main doctor | Tee-Object -FilePath cloud-doctor.txt
} else {
    throw "Python launcher was not found after installation. Restart Windows and rerun the script."
}

if (Test-Path "apps\mobile-cad-chatgpt\package-lock.json") {
    npm --prefix apps/mobile-cad-chatgpt ci
}

@"
HS-CAD cloud Windows bootstrap completed.

Workspace: $Workspace
Doctor report: $(Join-Path $Workspace 'cloud-doctor.txt')

Still requires manual licensed installation:
- ZWCAD 2025/2026
- Rhino 8
- Vendor GPU driver when the cloud provider does not preinstall it

Do not place API keys, GitHub runner tokens, CAD license files, or database service-role keys in the repository.
Use GitHub Codespaces secrets, repository/environment secrets, or the cloud provider's secret store.
"@ | Write-Host
