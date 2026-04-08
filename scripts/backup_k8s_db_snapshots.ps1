param(
    [string]$OutputPath,
    [switch]$SkipIfTransientState
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "db_snapshot_common.ps1")

if (-not $OutputPath) {
    $OutputPath = Get-DefaultSnapshotDirectory -RepoRoot $repoRoot
}

if ($SkipIfTransientState) {
    $seatInventoryTarget = Get-DbSnapshotTargetByName -Name "seat-inventory-service-db"
    $transferTarget = Get-DbSnapshotTargetByName -Name "transfer-service-db"

    $activeSeatHolds = [int](Invoke-DbPodSql -Target $seatInventoryTarget -Sql 'SELECT COUNT(*) FROM seat_inventory WHERE status = ''held'';')
    $activeTransfers = [int](Invoke-DbPodSql -Target $transferTarget -Sql 'SELECT COUNT(*) FROM transfers WHERE status IN (''pending_seller_acceptance'', ''pending_seller_otp'', ''pending_buyer_otp'') AND "expiresAt" > NOW();')

    if ($activeSeatHolds -gt 0 -or $activeTransfers -gt 0) {
        Write-Host "Skipping snapshot because transient workflow state is still active."
        Write-Host "Active seat holds: $activeSeatHolds"
        Write-Host "Active pending transfers: $activeTransfers"
        exit 0
    }
}

New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null

$targets = Get-DbSnapshotTargets
$manifestSnapshotPath = $OutputPath
try {
    $repoRootPath = [System.IO.Path]::GetFullPath($repoRoot)
    $outputPathResolved = [System.IO.Path]::GetFullPath($OutputPath)
    $repoRootPrefix = $repoRootPath.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if ($outputPathResolved.StartsWith($repoRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        $manifestSnapshotPath = [System.IO.Path]::GetRelativePath($repoRootPath, $outputPathResolved)
    }
} catch {
    # Keep the absolute path if relative-path derivation fails for any reason.
}

$manifest = [ordered]@{
    snapshotType = "ticketremaster-k8s-postgres"
    createdAt = (Get-Date).ToUniversalTime().ToString("o")
    snapshotPath = $manifestSnapshotPath
    databases = @()
}

foreach ($target in $targets) {
    $dumpPath = Join-Path $OutputPath $target.FileName
    Write-Host "Backing up $($target.Name) ($($target.Database)) -> $dumpPath"

    $dump = & kubectl exec -n $target.Namespace $target.Pod -c postgres -- sh -lc 'export PGPASSWORD="$POSTGRES_PASSWORD"; pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges --encoding=UTF8'
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to back up $($target.Name)"
    }
    if ([string]::IsNullOrWhiteSpace((($dump | Out-String).Trim()))) {
        throw "Backup for $($target.Name) produced an empty dump."
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
