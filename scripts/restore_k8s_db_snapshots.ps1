param(
    [string]$SnapshotPath,
    [switch]$SkipSeedJobs
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "db_snapshot_common.ps1")

if (-not $SnapshotPath) {
    $SnapshotPath = Get-DefaultSnapshotDirectory -RepoRoot $repoRoot
}

if (-not (Test-Path $SnapshotPath)) {
    throw "Snapshot path not found: $SnapshotPath"
}

$missingDumpFiles = Get-MissingDbSnapshotFiles -SnapshotPath $SnapshotPath
if ($missingDumpFiles.Count -gt 0) {
    throw "Snapshot is incomplete. Missing dump files: $($missingDumpFiles -join ', ')"
}

$targets = Get-DbSnapshotTargets
$restoredCount = 0

foreach ($target in $targets) {
    $dumpPath = Join-Path $SnapshotPath $target.FileName

    $remotePath = "/tmp/$($target.FileName)"
    Write-Host "Restoring $($target.Name) ($($target.Database)) from $dumpPath"

    & kubectl cp $dumpPath "$($target.Namespace)/$($target.Pod):$remotePath" -c postgres
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy dump for $($target.Name)"
    }

    & kubectl exec -n $target.Namespace $target.Pod -c postgres -- sh -lc "export PGPASSWORD=`"`$POSTGRES_PASSWORD`"; psql -v ON_ERROR_STOP=1 -U `"`$POSTGRES_USER`" -d `"`$POSTGRES_DB`" -f $remotePath"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to restore $($target.Name)"
    }

    & kubectl exec -n $target.Namespace $target.Pod -c postgres -- rm -f $remotePath | Out-Null
    $restoredCount += 1
}

Write-Host ""
Write-Host "Restore complete. Restored $restoredCount database dump(s)."

$seatInventoryTarget = Get-DbSnapshotTargetByName -Name "seat-inventory-service-db"
$transferTarget = Get-DbSnapshotTargetByName -Name "transfer-service-db"

$releasedHolds = Invoke-DbPodSql -Target $seatInventoryTarget -Sql @'
WITH released AS (
    UPDATE seat_inventory
       SET status = 'available',
           "heldByUserId" = NULL,
           "holdToken" = NULL,
           "heldUntil" = NULL,
           "updatedAt" = NOW()
     WHERE status = 'held'
       AND ("heldUntil" IS NULL OR "heldUntil" <= NOW())
 RETURNING 1
)
SELECT COUNT(*) FROM released;
'@

$expiredTransfers = Invoke-DbPodSql -Target $transferTarget -Sql @'
WITH expired AS (
    UPDATE transfers
       SET status = 'expired'
     WHERE status IN ('pending_seller_acceptance', 'pending_seller_otp', 'pending_buyer_otp')
       AND "expiresAt" <= NOW()
 RETURNING 1
)
SELECT COUNT(*) FROM expired;
'@

Write-Host "Expired transient state cleanup:"
Write-Host "  Released expired seat holds: $releasedHolds"
Write-Host "  Expired stale transfers: $expiredTransfers"

if (-not $SkipSeedJobs) {
    Write-Host "Re-running seed jobs to backfill any baseline rows missing from the snapshot..."
    & (Join-Path $PSScriptRoot "rerun_k8s_seeds.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Seed replay failed after restore."
    }
}
