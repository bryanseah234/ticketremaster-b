param(
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "db_snapshot_common.ps1")

if (-not $OutputPath) {
    $OutputPath = Get-DefaultSnapshotDirectory -RepoRoot $repoRoot
}

New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null

$targets = Get-DbSnapshotTargets
$manifest = [ordered]@{
    snapshotType = "ticketremaster-k8s-postgres"
    createdAt = (Get-Date).ToUniversalTime().ToString("o")
    snapshotPath = $OutputPath
    databases = @()
}

foreach ($target in $targets) {
    $dumpPath = Join-Path $OutputPath $target.FileName
    Write-Host "Backing up $($target.Name) ($($target.Database)) -> $dumpPath"

    $dump = & kubectl exec -n $target.Namespace $target.Pod -c postgres -- sh -lc 'export PGPASSWORD="$POSTGRES_PASSWORD"; pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges --encoding=UTF8'
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to back up $($target.Name)"
    }

    Set-Content -Path $dumpPath -Value $dump -Encoding utf8NoBOM
    $manifest.databases += [ordered]@{
        name = $target.Name
        namespace = $target.Namespace
        pod = $target.Pod
        database = $target.Database
        file = $target.FileName
    }
}

$manifestPath = Join-Path $OutputPath "manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Path $manifestPath -Encoding utf8NoBOM

Write-Host ""
Write-Host "Snapshot complete. Files written to $OutputPath"
