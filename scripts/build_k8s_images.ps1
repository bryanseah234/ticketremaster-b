param(
    [string]$Tag = "local-k8s-20260329"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

$images = @(
    @{ Name = "ticketremaster/user-service"; Context = "services/user-service" },
    @{ Name = "ticketremaster/venue-service"; Context = "services/venue-service" },
    @{ Name = "ticketremaster/seat-service"; Context = "services/seat-service" },
    @{ Name = "ticketremaster/event-service"; Context = "services/event-service" },
    @{ Name = "ticketremaster/seat-inventory-service"; Context = "services/seat-inventory-service" },
    @{ Name = "ticketremaster/ticket-service"; Context = "services/ticket-service" },
    @{ Name = "ticketremaster/ticket-log-service"; Context = "services/ticket-log-service" },
    @{ Name = "ticketremaster/marketplace-service"; Context = "services/marketplace-service" },
    @{ Name = "ticketremaster/transfer-service"; Context = "services/transfer-service" },
    @{ Name = "ticketremaster/credit-transaction-service"; Context = "services/credit-transaction-service" },
    @{ Name = "ticketremaster/stripe-wrapper"; Context = "services/stripe-wrapper" },
    @{ Name = "ticketremaster/otp-wrapper"; Context = "services/otp-wrapper" },
    @{ Name = "ticketremaster/auth-orchestrator"; Context = "orchestrators/auth-orchestrator" },
    @{ Name = "ticketremaster/event-orchestrator"; Context = "orchestrators/event-orchestrator" },
    @{ Name = "ticketremaster/credit-orchestrator"; Context = "orchestrators/credit-orchestrator" },
    @{ Name = "ticketremaster/ticket-purchase-orchestrator"; Context = "."; Dockerfile = "orchestrators/ticket-purchase-orchestrator/Dockerfile" },
    @{ Name = "ticketremaster/qr-orchestrator"; Context = "orchestrators/qr-orchestrator" },
    @{ Name = "ticketremaster/marketplace-orchestrator"; Context = "orchestrators/marketplace-orchestrator" },
    @{ Name = "ticketremaster/transfer-orchestrator"; Context = "."; Dockerfile = "orchestrators/transfer-orchestrator/Dockerfile" },
    @{ Name = "ticketremaster/ticket-verification-orchestrator"; Context = "orchestrators/ticket-verification-orchestrator" }
)

foreach ($image in $images) {
    $fullTag = "$($image.Name):$Tag"
    Write-Host "Building $fullTag"

    $contextPath = Join-Path $repoRoot $image.Context
    $dockerArgs = @("build", "--tag", $fullTag)

    if ($image.ContainsKey("Dockerfile")) {
        $dockerArgs += @("--file", (Join-Path $repoRoot $image.Dockerfile))
    }

    $dockerArgs += $contextPath

    & docker @dockerArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build $fullTag"
    }
}

Write-Host "Built $($images.Count) images with tag $Tag"
