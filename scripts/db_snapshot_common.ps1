$script:TicketRemasterDataNamespace = "ticketremaster-data"

function Get-DbSnapshotTargets {
    @(
        [pscustomobject]@{ Name = "user-service-db"; Namespace = $script:TicketRemasterDataNamespace; Pod = "user-service-db-0"; Database = "user_service"; FileName = "01-user-service.sql" }
        [pscustomobject]@{ Name = "venue-service-db"; Namespace = $script:TicketRemasterDataNamespace; Pod = "venue-service-db-0"; Database = "venue_service"; FileName = "02-venue-service.sql" }
        [pscustomobject]@{ Name = "seat-service-db"; Namespace = $script:TicketRemasterDataNamespace; Pod = "seat-service-db-0"; Database = "seat_service"; FileName = "03-seat-service.sql" }
        [pscustomobject]@{ Name = "event-service-db"; Namespace = $script:TicketRemasterDataNamespace; Pod = "event-service-db-0"; Database = "event_service"; FileName = "04-event-service.sql" }
        [pscustomobject]@{ Name = "seat-inventory-service-db"; Namespace = $script:TicketRemasterDataNamespace; Pod = "seat-inventory-service-db-0"; Database = "seat_inventory_service"; FileName = "05-seat-inventory-service.sql" }
        [pscustomobject]@{ Name = "credit-transaction-service-db"; Namespace = $script:TicketRemasterDataNamespace; Pod = "credit-transaction-service-db-0"; Database = "credit_transaction_service"; FileName = "06-credit-transaction-service.sql" }
        [pscustomobject]@{ Name = "ticket-service-db"; Namespace = $script:TicketRemasterDataNamespace; Pod = "ticket-service-db-0"; Database = "ticket_service"; FileName = "07-ticket-service.sql" }
        [pscustomobject]@{ Name = "ticket-log-service-db"; Namespace = $script:TicketRemasterDataNamespace; Pod = "ticket-log-service-db-0"; Database = "ticket_log_service"; FileName = "08-ticket-log-service.sql" }
        [pscustomobject]@{ Name = "marketplace-service-db"; Namespace = $script:TicketRemasterDataNamespace; Pod = "marketplace-service-db-0"; Database = "marketplace_service"; FileName = "09-marketplace-service.sql" }
        [pscustomobject]@{ Name = "transfer-service-db"; Namespace = $script:TicketRemasterDataNamespace; Pod = "transfer-service-db-0"; Database = "transfer_service"; FileName = "10-transfer-service.sql" }
    )
}

function Get-DefaultSnapshotDirectory {
    param(
        [Parameter(Mandatory)]
        [string]$RepoRoot
    )

    Join-Path (Join-Path (Join-Path $RepoRoot "db-snapshots") "k8s") "latest"
}

function Get-MissingDbSnapshotFiles {
    param(
        [Parameter(Mandatory)]
        [string]$SnapshotPath
    )

    @(
        Get-DbSnapshotTargets |
            Where-Object { -not (Test-Path (Join-Path $SnapshotPath $_.FileName)) } |
            ForEach-Object { $_.FileName }
    )
}

function Test-DbSnapshotAvailable {
    param(
        [Parameter(Mandatory)]
        [string]$SnapshotPath
    )

    (Get-MissingDbSnapshotFiles -SnapshotPath $SnapshotPath).Count -eq 0
}

function Invoke-DbPodSql {
    param(
        [Parameter(Mandatory)]
        [pscustomobject]$Target,
        [Parameter(Mandatory)]
        [string]$Sql
    )

    # Stream SQL over stdin so PowerShell does not mangle quoted identifiers in native command arguments.
    $command = 'export PGPASSWORD=$POSTGRES_PASSWORD; psql -X -A -t -v ON_ERROR_STOP=1 -U $POSTGRES_USER -d $POSTGRES_DB'
    $sqlInput = if ($Sql.EndsWith("`n")) { $Sql } else { "$Sql`n" }
    $result = $sqlInput | & kubectl exec -i -n $Target.Namespace $Target.Pod -c postgres -- sh -lc $command
    if ($LASTEXITCODE -ne 0) {
        throw "Failed SQL query against $($Target.Name)"
    }

    (($result | Out-String).Trim())
}

function Get-DbSnapshotTargetByName {
    param(
        [Parameter(Mandatory)]
        [string]$Name
    )

    Get-DbSnapshotTargets | Where-Object { $_.Name -eq $Name } | Select-Object -First 1
}
