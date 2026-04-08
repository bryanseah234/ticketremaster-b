param(
    [string]$Tag = "local-k8s-20260329",
    [Alias("Images")]
    [string[]]$TargetImages
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

$imageDefinitions = @(
    @{ Name = "ticketremaster/user-service"; Context = "."; Dockerfile = "services/user-service/Dockerfile" },
    @{ Name = "ticketremaster/venue-service"; Context = "services/venue-service" },
    @{ Name = "ticketremaster/seat-service"; Context = "services/seat-service" },
    @{ Name = "ticketremaster/event-service"; Context = "."; Dockerfile = "services/event-service/Dockerfile" },
    @{ Name = "ticketremaster/seat-inventory-service"; Context = "."; Dockerfile = "services/seat-inventory-service/Dockerfile" },
    @{ Name = "ticketremaster/ticket-service"; Context = "."; Dockerfile = "services/ticket-service/Dockerfile" },
    @{ Name = "ticketremaster/ticket-log-service"; Context = "services/ticket-log-service" },
    @{ Name = "ticketremaster/marketplace-service"; Context = "services/marketplace-service" },
    @{ Name = "ticketremaster/transfer-service"; Context = "services/transfer-service" },
    @{ Name = "ticketremaster/credit-transaction-service"; Context = "services/credit-transaction-service" },
    @{ Name = "ticketremaster/stripe-wrapper"; Context = "services/stripe-wrapper" },
    @{ Name = "ticketremaster/otp-wrapper"; Context = "services/otp-wrapper" },
    @{ Name = "ticketremaster/auth-orchestrator"; Context = "."; Dockerfile = "orchestrators/auth-orchestrator/Dockerfile" },
    @{ Name = "ticketremaster/event-orchestrator"; Context = "."; Dockerfile = "orchestrators/event-orchestrator/Dockerfile" },
    @{ Name = "ticketremaster/credit-orchestrator"; Context = "orchestrators/credit-orchestrator" },
    @{ Name = "ticketremaster/ticket-purchase-orchestrator"; Context = "."; Dockerfile = "orchestrators/ticket-purchase-orchestrator/Dockerfile" },
    @{ Name = "ticketremaster/qr-orchestrator"; Context = "orchestrators/qr-orchestrator" },
    @{ Name = "ticketremaster/marketplace-orchestrator"; Context = "orchestrators/marketplace-orchestrator" },
    @{ Name = "ticketremaster/transfer-orchestrator"; Context = "."; Dockerfile = "orchestrators/transfer-orchestrator/Dockerfile" },
    @{ Name = "ticketremaster/ticket-verification-orchestrator"; Context = "orchestrators/ticket-verification-orchestrator" }
)

$selectedImages = @($imageDefinitions)
if ($TargetImages -and $TargetImages.Count -gt 0) {
    $requested = @(
        $TargetImages |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ } |
        Select-Object -Unique
    )

    $filtered = @()
    $unknown = @()

    foreach ($requestedImage in $requested) {
        $match = $null
        foreach ($image in $imageDefinitions) {
            $fullTag = "$($image.Name):$Tag"
            if ($requestedImage -eq $image.Name -or $requestedImage -eq $fullTag) {
                $match = $image
                break
            }
        }

        if ($null -eq $match) {
            $unknown += $requestedImage
        } elseif (-not ($filtered | Where-Object { $_.Name -eq $match.Name })) {
            $filtered += $match
        }
    }

    if ($unknown.Count -gt 0) {
        throw "Unknown image name(s): $($unknown -join ', ')"
    }

    $selectedImages = $filtered
}

if ($selectedImages.Count -eq 0) {
    Write-Host "No images selected for build."
    exit 0
}

foreach ($image in $selectedImages) {
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

Write-Host "Built $($selectedImages.Count) images with tag $Tag"
