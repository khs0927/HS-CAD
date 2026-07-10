[CmdletBinding()]
param(
    [string]$Executable = "",
    [string]$Database = "$env:LOCALAPPDATA\HS-CAD\xicad-jobs.sqlite3",
    [ValidateSet("2024", "2025", "2026")]
    [string]$ZwcadVersion = "2026",
    [string]$TaskName = "HS-CAD XiCAD Background Worker",
    [switch]$Hidden,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task: $TaskName" -ForegroundColor Yellow
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Executable)) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\HS-CAD\HS-CAD.exe",
        (Join-Path (Split-Path -Parent $PSScriptRoot) "dist\HS-CAD.exe")
    )
    $Executable = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $Executable -or -not (Test-Path $Executable)) {
    throw "HS-CAD.exe not found. Pass -Executable with the installed or portable EXE path."
}

$databaseDir = Split-Path -Parent $Database
New-Item -ItemType Directory -Force $databaseDir | Out-Null

$visibility = if ($Hidden) { "--hidden" } else { "--visible" }
$arguments = "xicad-bg-worker --db `"$Database`" --zwcad-version $ZwcadVersion $visibility --poll-seconds 2"
$action = New-ScheduledTaskAction -Execute (Resolve-Path $Executable) -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Consumes safety-approved XiCAD architectural automation jobs from the HS-CAD SQLite queue."

Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Installed and started: $TaskName" -ForegroundColor Green
Write-Host "Queue database: $Database"
