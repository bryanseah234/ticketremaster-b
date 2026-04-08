param(
    [string]$ManifestPath = (Join-Path (Split-Path -Parent $PSScriptRoot) "k8s\base\seed-jobs.yaml")
)

$ErrorActionPreference = "Stop"

$namespace = "ticketremaster-core"
$jobs = @(
    "seed-venues",
    "seed-events",
    "seed-seats",
    "seed-seat-inventory",
    "seed-users"
)

foreach ($workload in @(
    "deployment/venue-service",
    "deployment/event-service",
    "deployment/seat-service",
    "deployment/seat-inventory-service",
    "deployment/user-service"
)) {
    & kubectl rollout status $workload --namespace $namespace --timeout=10m
    if ($LASTEXITCODE -ne 0) {
        throw "Failed waiting for $workload"
    }
}

& kubectl delete job --namespace $namespace --ignore-not-found @jobs
if ($LASTEXITCODE -ne 0) {
    throw "Failed deleting existing seed jobs"
}

& kubectl apply -f $ManifestPath
if ($LASTEXITCODE -ne 0) {
    throw "Failed applying $ManifestPath"
}

foreach ($job in $jobs) {
    & kubectl wait --namespace $namespace --for=condition=complete --timeout=20m "job/$job"
    if ($LASTEXITCODE -ne 0) {
        throw "Seed job $job did not complete successfully"
    }

    Write-Host "$job completed"
}
