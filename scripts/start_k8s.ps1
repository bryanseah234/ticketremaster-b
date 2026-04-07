#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Apply the TicketRemaster Kubernetes stack, wait for it to become usable,
    start a Kong port-forward, then run the Newman gateway smoke suite.

.USAGE
    cd ticketremaster-b
    .\scripts\start_k8s.ps1

    Optional flags:
    -SkipImageLoad   Skip loading Docker images into Minikube
    -SkipPortForward Skip opening a new localhost:8000 port-forward window
    -PublicOnly      Skip localhost tests and run only the Cloudflare smoke suite
    -RunPublicTests  Run the Cloudflare smoke suite after localhost checks
#>
param(
    [switch]$SkipImageLoad,
    [switch]$SkipPortForward,
    [switch]$PublicOnly,
    [switch]$RunPublicTests
)

$ErrorActionPreference = "Stop"
$Tag = "local-k8s-20260329"
$repoRoot = Split-Path -Parent $PSScriptRoot
$script:LocalGatewayPort = 8000
$script:LocalGatewayUrl = "http://localhost:8000"

function Write-Step($Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-OK($Message) {
    Write-Host "    [OK] $Message" -ForegroundColor Green
}

function Write-Warn($Message) {
    Write-Host "    [!!] $Message" -ForegroundColor Yellow
}

function Invoke-External {
    param(
        [Parameter(Mandatory)]
        [string]$Command,
        [string[]]$Arguments = @(),
        [string]$ErrorMessage = "$Command failed."
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $ErrorMessage
    }
}

function Get-DesiredImages {
    @(
        "ticketremaster/user-service:$Tag",
        "ticketremaster/venue-service:$Tag",
        "ticketremaster/seat-service:$Tag",
        "ticketremaster/event-service:$Tag",
        "ticketremaster/seat-inventory-service:$Tag",
        "ticketremaster/ticket-service:$Tag",
        "ticketremaster/ticket-log-service:$Tag",
        "ticketremaster/marketplace-service:$Tag",
        "ticketremaster/transfer-service:$Tag",
        "ticketremaster/credit-transaction-service:$Tag",
        "ticketremaster/stripe-wrapper:$Tag",
        "ticketremaster/otp-wrapper:$Tag",
        "ticketremaster/auth-orchestrator:$Tag",
        "ticketremaster/event-orchestrator:$Tag",
        "ticketremaster/credit-orchestrator:$Tag",
        "ticketremaster/ticket-purchase-orchestrator:$Tag",
        "ticketremaster/qr-orchestrator:$Tag",
        "ticketremaster/marketplace-orchestrator:$Tag",
        "ticketremaster/transfer-orchestrator:$Tag",
        "ticketremaster/ticket-verification-orchestrator:$Tag"
    )
}

function Ensure-ImagesLoaded {
    Write-Step "Checking Minikube images"
    $desiredImages = Get-DesiredImages
    $loadedImagesText = (& minikube image list 2>&1) | Out-String
    $missingImages = @()

    foreach ($image in $desiredImages) {
        if ($loadedImagesText -notmatch [regex]::Escape($image)) {
            $missingImages += $image
        }
    }

    if ($missingImages.Count -eq 0) {
        Write-OK "All required images are already loaded in Minikube"
        return
    }

    Write-Warn "Missing $($missingImages.Count) image(s) in Minikube"
    $dockerImagesText = (& docker images --format "{{.Repository}}:{{.Tag}}" 2>&1) | Out-String
    $missingDockerImages = @()
    foreach ($image in $missingImages) {
        if ($dockerImagesText -notmatch [regex]::Escape($image)) {
            $missingDockerImages += $image
        }
    }

    if ($missingDockerImages.Count -gt 0) {
        Write-Warn "Building missing Docker images first"
        & "$PSScriptRoot\build_k8s_images.ps1" -Tag $Tag
        if ($LASTEXITCODE -ne 0) {
            throw "Docker image build failed."
        }
    }

    foreach ($image in $missingImages) {
        Write-Host "    Loading $image"
        Invoke-External -Command "minikube" -Arguments @("image", "load", $image) -ErrorMessage "Failed to load $image into Minikube."
    }

    Write-OK "Required images are loaded"
}

function Get-KubernetesNames {
    param(
        [Parameter(Mandatory)]
        [ValidateSet("deployment", "statefulset", "job")]
        [string]$Kind,
        [Parameter(Mandatory)]
        [string]$Namespace
    )

    $result = & kubectl get $Kind -n $Namespace -o name
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to list $Kind resources in namespace $Namespace."
    }

    return @(
        $result -split "`r?`n" |
        Where-Object { $_ -and $_.Trim() } |
        ForEach-Object { ($_ -split '/', 2)[-1] }
    )
}

function Wait-StatefulSetsReady {
    param([Parameter(Mandatory)][string]$Namespace)

    $names = Get-KubernetesNames -Kind statefulset -Namespace $Namespace
    if ($names.Count -eq 0) {
        Write-OK "No StatefulSets found in $Namespace"
        return
    }

    foreach ($name in $names) {
        Write-Host "    Waiting for statefulset/$name..."
        Invoke-External -Command "kubectl" -Arguments @("rollout", "status", "statefulset/$name", "-n", $Namespace, "--timeout=300s") -ErrorMessage "StatefulSet $name in $Namespace did not become ready."
    }
}

function Wait-DeploymentsReady {
    param(
        [Parameter(Mandatory)][string]$Namespace,
        [string[]]$Names
    )

    $targetNames = if ($Names -and $Names.Count -gt 0) { $Names } else { Get-KubernetesNames -Kind deployment -Namespace $Namespace }
    if ($targetNames.Count -eq 0) {
        Write-OK "No Deployments found in $Namespace"
        return
    }

    foreach ($name in $targetNames) {
        Write-Host "    Waiting for deployment/$name..."
        Invoke-External -Command "kubectl" -Arguments @("rollout", "status", "deployment/$name", "-n", $Namespace, "--timeout=300s") -ErrorMessage "Deployment $name in $Namespace did not become ready."
    }
}

function Try-WaitDeploymentReady {
    param(
        [Parameter(Mandatory)][string]$Namespace,
        [Parameter(Mandatory)][string]$Name,
        [int]$TimeoutSeconds = 300
    )

    try {
        Write-Host "    Waiting for deployment/$Name..."
        Invoke-External -Command "kubectl" -Arguments @("rollout", "status", "deployment/$Name", "-n", $Namespace, "--timeout=${TimeoutSeconds}s") -ErrorMessage "Deployment $Name in $Namespace did not become ready."
        return $true
    } catch {
        Write-Warn $_.Exception.Message
        return $false
    }
}

function Wait-JobsComplete {
    param([Parameter(Mandatory)][string]$Namespace)

    $names = Get-KubernetesNames -Kind job -Namespace $Namespace
    if ($names.Count -eq 0) {
        Write-OK "No Jobs found in $Namespace"
        return
    }

    foreach ($name in $names) {
        Write-Host "    Waiting for job/$name..."
        Invoke-External -Command "kubectl" -Arguments @("wait", "--for=condition=complete", "job/$name", "-n", $Namespace, "--timeout=600s") -ErrorMessage "Job $name in $Namespace did not complete."
    }
}

function Wait-HttpEndpoint {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Url,
        [int[]]$ExpectedStatusCodes = @(200),
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -TimeoutSec 5 -UseBasicParsing
            if ($ExpectedStatusCodes -contains [int]$response.StatusCode) {
                Write-OK "$Name is responding at $Url"
                return
            }
        } catch {
            if ($_.Exception.Response -and $ExpectedStatusCodes -contains [int]$_.Exception.Response.StatusCode.value__) {
                Write-OK "$Name is responding at $Url"
                return
            }
        }
        Start-Sleep -Seconds 3
    }

    throw "$Name did not become reachable at $Url within $TimeoutSeconds seconds."
}

function Test-KongGateway {
    param(
        [Parameter(Mandatory)][string]$Url,
        [int]$TimeoutSeconds = 5
    )

    try {
        $response = Invoke-WebRequest -Uri "$Url/events" -TimeoutSec $TimeoutSeconds -UseBasicParsing
        $contentType = (($response.Headers['Content-Type'] | Select-Object -First 1) -as [string])
        if (-not $contentType) {
            $contentType = [string]$response.ContentType
        }
        if ($response.StatusCode -ne 200) {
            return $false
        }
        if ($contentType -notmatch 'application/json') {
            return $false
        }
        $body = $response.Content | ConvertFrom-Json -ErrorAction Stop
        return ($null -ne $body.data -or $null -ne $body.events)
    } catch {
        return $false
    }
}

function Get-FreeTcpPort {
    param(
        [int[]]$Candidates = @(8000, 18000, 18080, 28000)
    )

    foreach ($candidate in $Candidates) {
        $listener = Get-NetTCPConnection -LocalPort $candidate -State Listen -ErrorAction SilentlyContinue
        if (-not $listener) {
            return $candidate
        }
    }

    throw "Could not find a free local port for the Kong port-forward."
}

function Ensure-PortForward {
    if ($SkipPortForward -or $PublicOnly) {
        return
    }

    Write-Step "Ensuring Kong port-forward is available locally"

    $preferredPort = 8000
    if (Test-KongGateway -Url "http://localhost:$preferredPort") {
        $script:LocalGatewayPort = $preferredPort
        $script:LocalGatewayUrl = "http://localhost:$preferredPort"
        Write-OK "Existing Kong listener detected on $script:LocalGatewayUrl"
        return
    }

    $portInUse = Get-NetTCPConnection -LocalPort $preferredPort -State Listen -ErrorAction SilentlyContinue
    if ($portInUse) {
        Write-Warn "Port $preferredPort is already in use by a non-Kong service. Selecting a fallback port."
        $script:LocalGatewayPort = Get-FreeTcpPort
    } else {
        $script:LocalGatewayPort = $preferredPort
    }

    $script:LocalGatewayUrl = "http://localhost:$script:LocalGatewayPort"
    Start-Process powershell -ArgumentList "-NoExit -Command kubectl port-forward -n ticketremaster-edge service/kong-proxy $script:LocalGatewayPort`:80" -WindowStyle Minimized | Out-Null
    Start-Sleep -Seconds 3

    if (-not (Test-KongGateway -Url $script:LocalGatewayUrl)) {
        Wait-HttpEndpoint -Name "Local Kong gateway" -Url "$script:LocalGatewayUrl/events" -ExpectedStatusCodes @(200)
        if (-not (Test-KongGateway -Url $script:LocalGatewayUrl)) {
            throw "A listener is reachable at $script:LocalGatewayUrl but it does not appear to be the Kong gateway."
        }
    }

    Write-OK "Kong is available at $script:LocalGatewayUrl"
}

if ($PublicOnly -and -not $RunPublicTests) {
    throw "PublicOnly requires RunPublicTests."
}

Write-Step "Checking prerequisites"
foreach ($cmd in @("docker", "kubectl", "minikube", "newman")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "$cmd not found. Install it first."
    }
    Write-OK "$cmd found"
}

Write-Step "Checking Minikube"
& kubectl get nodes --request-timeout=10s | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Minikube is not running or the API server is unreachable. Run: minikube start"
}
Write-OK "Minikube is up"

if (-not $SkipImageLoad) {
    Ensure-ImagesLoaded
}

Write-Step "Applying k8s manifests"
Invoke-External -Command "kubectl" -Arguments @("apply", "-k", "k8s/base", "--request-timeout=30s") -ErrorMessage "kubectl apply failed."
Write-OK "Manifests applied"

Write-Step "Waiting for data plane statefulsets"
Wait-StatefulSetsReady -Namespace "ticketremaster-data"
Write-OK "Data plane ready"

Write-Step "Waiting for core deployments"
Wait-DeploymentsReady -Namespace "ticketremaster-core"
Write-OK "Core deployments ready"

Write-Step "Waiting for edge deployments"
Wait-DeploymentsReady -Namespace "ticketremaster-edge" -Names @("kong")
Write-OK "Kong is ready"

Write-Step "Waiting for seed jobs"
Wait-JobsComplete -Namespace "ticketremaster-core"
Write-OK "Seed jobs completed"

Ensure-PortForward

$canRunPublicTests = $RunPublicTests
if ($RunPublicTests) {
    Write-Step "Checking Cloudflare tunnel readiness"
    $cloudflaredReady = Try-WaitDeploymentReady -Namespace "ticketremaster-edge" -Name "cloudflared" -TimeoutSeconds 180
    if (-not $cloudflaredReady) {
        Write-Warn "Cloudflared rollout did not report ready. Checking the public URL directly before skipping public tests."
    }

    try {
        Wait-HttpEndpoint -Name "Public gateway" -Url "https://ticketremasterapi.hong-yi.me/events" -ExpectedStatusCodes @(200) -TimeoutSeconds 180
    } catch {
        Write-Warn $_.Exception.Message
        Write-Warn "Public URL is not reachable yet. Continuing with localhost only."
        $canRunPublicTests = $false
    }
}

Write-Step "Running gateway smoke tests"
if (-not $PublicOnly) {
    Write-Host "`n--- Localhost via Kong ---" -ForegroundColor White
    Invoke-External -Command "newman" -Arguments @(
        "run",
        "postman/TicketRemaster.gateway.postman_collection.json",
        "-e", "postman/TicketRemaster.gateway-localhost.postman_environment.json",
        "--env-var", "gateway_url=$script:LocalGatewayUrl",
        "--reporters", "cli"
    ) -ErrorMessage "Localhost Newman smoke tests failed."
}

if ($canRunPublicTests) {
    Write-Host "`n--- Public URL via Cloudflare ---" -ForegroundColor White
    Invoke-External -Command "newman" -Arguments @(
        "run",
        "postman/TicketRemaster.gateway.postman_collection.json",
        "-e", "postman/TicketRemaster.gateway-public.postman_environment.json",
        "--reporters", "cli"
    ) -ErrorMessage "Public Newman smoke tests failed."
} elseif ($PublicOnly) {
    throw "PublicOnly was requested but RunPublicTests was not enabled."
} else {
    Write-Warn "Public smoke tests skipped because no Cloudflare tunnel token was requested."
}

Write-Step "Done"
Write-Host "    Local gateway: $script:LocalGatewayUrl" -ForegroundColor Green
if ($canRunPublicTests) {
    Write-Host "    Public gateway: https://ticketremasterapi.hong-yi.me" -ForegroundColor Green
} elseif ($RunPublicTests) {
    Write-Host "    Public gateway: not ready yet (cloudflared or public endpoint still reconnecting)" -ForegroundColor Yellow
}
