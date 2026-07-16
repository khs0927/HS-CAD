[CmdletBinding()]
param(
    [string]$ExpectedWorkerUrl = "",
    [switch]$SkipInstall,
    [switch]$SkipDeploy,
    [switch]$AllowUncommitted,
    [int]$HealthRetries = 12,
    [int]$HealthRetrySeconds = 5
)

$ErrorActionPreference = "Stop"
$appRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$repoRoot = Split-Path -Parent (Split-Path -Parent $appRoot)
Set-Location $appRoot

function Assert-LastExitCode([string]$Message) {
    if ($LASTEXITCODE -ne 0) { throw $Message }
}

function Get-NodeVersion {
    $raw = (& node --version).Trim().TrimStart("v")
    return [version]$raw
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js is not installed. Install Node.js 22.18 or newer."
}
$nodeVersion = Get-NodeVersion
if ($nodeVersion -lt [version]"22.18.0") {
    throw "Node.js 22.18 or newer is required. Found: $nodeVersion"
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is not available."
}

if (-not $AllowUncommitted) {
    Push-Location $repoRoot
    try {
        $status = (& git status --short --untracked-files=all) -join "`n"
        Assert-LastExitCode "Unable to inspect git status."
        if ($status.Trim()) {
            throw "Working tree is not clean. Commit/stash intended changes or rerun with -AllowUncommitted after reviewing them."
        }
    } finally {
        Pop-Location
    }
}

$logsDir = Join-Path $appRoot "deployment-logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$validateLog = Join-Path $logsDir "$timestamp-validate.log"
$deployLog = Join-Path $logsDir "$timestamp-deploy.log"
$resultPath = Join-Path $appRoot "CODEX_DEPLOYMENT_RESULT.md"

if (-not $SkipInstall) {
    Write-Host "[HS-CAD mobile] Installing exact declared dependencies"
    & npm install --ignore-scripts --no-audit --no-fund --package-lock=false
    Assert-LastExitCode "npm install failed."
}

Write-Host "[HS-CAD mobile] Running source, test, build, and Worker dry-run validation"
& npm run validate:ci 2>&1 | Tee-Object -FilePath $validateLog
Assert-LastExitCode "npm run validate:ci failed."

Write-Host "[HS-CAD mobile] Verifying Cloudflare authentication"
& npx wrangler whoami
Assert-LastExitCode "Cloudflare authentication is missing or invalid. Run npx wrangler login with the user's approval."

$workerUrl = $ExpectedWorkerUrl.Trim().TrimEnd("/")
if (-not $SkipDeploy) {
    Write-Host "[HS-CAD mobile] Deploying Cloudflare Worker"
    $deployOutput = (& npx wrangler deploy 2>&1 | Tee-Object -FilePath $deployLog) -join "`n"
    Assert-LastExitCode "wrangler deploy failed."

    if (-not $workerUrl) {
        $matches = [regex]::Matches($deployOutput, "https://[A-Za-z0-9._-]+\.workers\.dev")
        if ($matches.Count -gt 0) {
            $workerUrl = $matches[$matches.Count - 1].Value.TrimEnd("/")
        }
    }
}

if (-not $workerUrl) {
    throw "Could not determine the deployed workers.dev URL. Rerun with -ExpectedWorkerUrl https://<worker>.workers.dev"
}

$healthUrl = "$workerUrl/health"
$mcpUrl = "$workerUrl/mcp"
$healthPayload = $null
$healthError = ""
for ($attempt = 1; $attempt -le $HealthRetries; $attempt++) {
    try {
        $healthPayload = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 30
        if ($healthPayload.ok -eq $true) { break }
        $healthError = "Health payload did not contain ok=true: $($healthPayload | ConvertTo-Json -Compress)"
    } catch {
        $healthError = $_.Exception.Message
    }
    if ($attempt -lt $HealthRetries) {
        Start-Sleep -Seconds $HealthRetrySeconds
    }
}

if ($null -eq $healthPayload -or $healthPayload.ok -ne $true) {
    throw "Deployed Worker health check failed after $HealthRetries attempts. $healthError"
}

$healthJson = $healthPayload | ConvertTo-Json -Depth 10 -Compress
$lines = @(
    "# Codex Cloudflare Deployment Result",
    "",
    "- Date: $(Get-Date -Format o)",
    "- Node.js: $nodeVersion",
    "- Worker URL: $workerUrl",
    "- Health URL: $healthUrl",
    "- MCP URL: $mcpUrl",
    "- Health response: $healthJson",
    "- Validation log: deployment-logs/$(Split-Path -Leaf $validateLog)",
    "- Deploy log: deployment-logs/$(Split-Path -Leaf $deployLog)",
    "",
    "## Next connected-account step",
    "",
    "Register the MCP URL in ChatGPT Developer Mode, refresh the app after registration, and execute the acceptance prompts in MOBILE_TEST_PROMPTS.md.",
    "",
    "## Security note",
    "",
    "Do not commit deployment logs when they contain account identifiers, tokens, private URLs, or other sensitive data. Commit only a manually reviewed and sanitized result summary.",
    ""
)
Set-Content -Path $resultPath -Value ($lines -join "`n") -Encoding utf8

Write-Host ""
Write-Host "Deployment verified."
Write-Host "Worker: $workerUrl"
Write-Host "MCP:    $mcpUrl"
Write-Host "Result: $resultPath"
