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

    Join-Path $RepoRoot "db-snapshots\k8s\latest"
}

function Test-DbSnapshotAvailable {
    param(
        [Parameter(Mandatory)]
        [string]$SnapshotPath
    )

    $targets = Get-DbSnapshotTargets
    foreach ($target in $targets) {
        $candidate = Join-Path $SnapshotPath $target.FileName
        if (Test-Path $candidate) {
            return $true
        }
    }

    return $false
}
