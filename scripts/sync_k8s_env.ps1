param(
    [string]$DotEnvPath = (Join-Path (Split-Path -Parent $PSScriptRoot) ".env")
)

$ErrorActionPreference = "Stop"

function Read-DotEnv {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        throw ".env file not found at $Path"
    }

    $values = @{}

    foreach ($line in Get-Content -Path $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $parts = $trimmed -split "=", 2
        if ($parts.Count -ne 2) {
            continue
        }

        $values[$parts[0]] = $parts[1]
    }

    return $values
}

function Resolve-Value {
    param(
        [hashtable]$Values,
        [string]$Key,
        [System.Collections.Generic.HashSet[string]]$Stack = $(New-Object 'System.Collections.Generic.HashSet[string]')
    )

    if (-not $Values.ContainsKey($Key)) {
        return $null
    }

    if ($Stack.Contains($Key)) {
        throw "Circular variable reference detected for $Key"
    }

    $null = $Stack.Add($Key)
    $resolved = [regex]::Replace($Values[$Key], '\$\{([^}]+)\}', {
        param($match)
        $name = $match.Groups[1].Value
        Resolve-Value -Values $Values -Key $name -Stack $Stack
    })
    $Stack.Remove($Key) | Out-Null
    return $resolved
}

function Resolve-AllValues {
    param([hashtable]$Values)

    $resolved = @{}
    foreach ($key in $Values.Keys) {
        $resolved[$key] = Resolve-Value -Values $Values -Key $key
    }
    return $resolved
}

function Apply-Secret {
    param(
        [string]$Namespace,
        [string]$Name,
        [hashtable]$Data
    )

    $args = @("create", "secret", "generic", $Name, "--namespace", $Namespace, "--dry-run=client", "-o", "yaml")

    foreach ($entry in $Data.GetEnumerator()) {
        if ([string]::IsNullOrWhiteSpace($entry.Value)) {
            throw "Missing value for $($entry.Key) in secret $Name"
        }

        $args += "--from-literal=$($entry.Key)=$($entry.Value)"
    }

    $yaml = & kubectl @args
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to generate secret manifest for $Namespace/$Name"
    }

    $yaml | & kubectl apply -f -
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to apply secret $Namespace/$Name"
    }

    Write-Host "Applied secret $Namespace/$Name"
}

$values = Resolve-AllValues -Values (Read-DotEnv -Path $DotEnvPath)

Apply-Secret -Namespace "ticketremaster-core" -Name "core-secrets" -Data @{
    JWT_SECRET = $values["JWT_SECRET"]
    QR_SECRET = $values["QR_SECRET"]
    OUTSYSTEMS_API_KEY = $values["OUTSYSTEMS_API_KEY"]
    STRIPE_SECRET_KEY = $values["STRIPE_SECRET_KEY"]
    STRIPE_WEBHOOK_SECRET = $values["STRIPE_WEBHOOK_SECRET"]
    SMU_API_KEY = $values["SMU_API_KEY"]
}

$sharedDataSecrets = @{
    RABBITMQ_USER = $values["RABBITMQ_USER"]
    RABBITMQ_PASS = $values["RABBITMQ_PASS"]
    USER_SERVICE_DB_PASSWORD = $values["USER_SERVICE_DB_PASSWORD"]
    VENUE_SERVICE_DB_PASSWORD = $values["VENUE_SERVICE_DB_PASSWORD"]
    SEAT_SERVICE_DB_PASSWORD = $values["SEAT_SERVICE_DB_PASSWORD"]
    EVENT_SERVICE_DB_PASSWORD = $values["EVENT_SERVICE_DB_PASSWORD"]
    SEAT_INVENTORY_SERVICE_DB_PASSWORD = $values["SEAT_INVENTORY_SERVICE_DB_PASSWORD"]
    CREDIT_TRANSACTION_SERVICE_DB_PASSWORD = $values["CREDIT_TRANSACTION_SERVICE_DB_PASSWORD"]
    TICKET_SERVICE_DB_PASSWORD = $values["TICKET_SERVICE_DB_PASSWORD"]
    TICKET_LOG_SERVICE_DB_PASSWORD = $values["TICKET_LOG_SERVICE_DB_PASSWORD"]
    MARKETPLACE_SERVICE_DB_PASSWORD = $values["MARKETPLACE_SERVICE_DB_PASSWORD"]
    TRANSFER_SERVICE_DB_PASSWORD = $values["TRANSFER_SERVICE_DB_PASSWORD"]
}

Apply-Secret -Namespace "ticketremaster-core" -Name "core-data-secrets" -Data $sharedDataSecrets
Apply-Secret -Namespace "ticketremaster-data" -Name "data-secrets" -Data $sharedDataSecrets
Apply-Secret -Namespace "ticketremaster-edge" -Name "edge-secrets" -Data @{
    CLOUDFLARE_TUNNEL_TOKEN = $values["CLOUDFLARE_TUNNEL_TOKEN"]
}
