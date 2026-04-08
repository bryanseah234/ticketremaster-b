param(
    [string]$TaskName = "TicketRemasterDbSnapshot",
    [int]$IntervalMinutes = 60
)

$ErrorActionPreference = "Stop"

if ($IntervalMinutes -lt 15) {
    throw "IntervalMinutes must be at least 15."
}

$scriptPath = Join-Path $PSScriptRoot "backup_k8s_db_snapshots.ps1"
if (-not (Test-Path $scriptPath)) {
    throw "Backup script not found: $scriptPath"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -SkipIfTransientState"

$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date.AddMinutes(5) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration ([TimeSpan]::MaxValue)

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "TicketRemaster Kubernetes DB snapshot backup that skips active transient workflow state." `
    -Force | Out-Null

Write-Host "Scheduled task '$TaskName' registered to run every $IntervalMinutes minute(s)."
Write-Host "The task runs backup_k8s_db_snapshots.ps1 -SkipIfTransientState"
