param([switch]$DeterministicOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$env:PYTHONPATH = 'backend;.'
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
New-Item -ItemType Directory -Force -Path '.local-tools\hybrid' | Out-Null
if ($DeterministicOnly) { $env:HYBRID_LLM_ENABLED = 'false' }
if (-not $DeterministicOnly) {
    & .\scripts\start_ollama.ps1 -NoWarmup -Model 'qwen3.5:2b-q4_K_M' `
        -ContextTokens 8192 -BatchTokens 128
    $admission = & $python -m scripts.hybrid_runtime | ConvertFrom-Json
    if ($admission.admitted -and $admission.owner_verified) {
    # One small host watcher; stale/missing measurements disable inference in the API.
    $pidFile = Join-Path $projectRoot '.local-tools\hybrid\watcher.pid'
    $watcherRunning = $false
    if (Test-Path -LiteralPath $pidFile) {
        $watcherId = [int](Get-Content -LiteralPath $pidFile)
        $watcherProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$watcherId"
        $watcherRunning = $watcherProcess.ExecutablePath -eq $python -and `
            $watcherProcess.CommandLine -match 'scripts.hybrid_runtime --watch'
    }
    if (-not $watcherRunning) {
        $watcher = Start-Process -FilePath $python -WindowStyle Hidden -PassThru `
            -ArgumentList '-m scripts.hybrid_runtime --watch' -WorkingDirectory $projectRoot `
            -RedirectStandardOutput '.local-tools\hybrid\watcher.stdout.log' `
            -RedirectStandardError '.local-tools\hybrid\watcher.stderr.log'
        $watcher.Id | Set-Content -LiteralPath $pidFile -Encoding utf8
    }
    & $python -m scripts.hybrid_runtime --warmup
    } else {
        Write-Output ('Local model startup BLOCKED: ' + ($admission.reasons -join '; '))
        Write-Output 'The verified deterministic API remains available. No model was loaded.'
    }
}
docker compose up -d --build api
if ($LASTEXITCODE -ne 0) { throw 'OpsPilot API startup failed.' }
