param(
    [switch]$Install,
    [switch]$PullModel,
    [switch]$NoWarmup,
    [string]$Model = 'qwen3.5:4b',
    [ValidateRange(8192, 32768)][int]$ContextTokens = 32768,
    [ValidateRange(32, 512)][int]$BatchTokens = 512
)
$ErrorActionPreference = 'Stop'
if ($Model -match '(?i)cloud') { throw 'Cloud models are disabled. Select a downloaded local model.' }
$projectRoot = Split-Path $PSScriptRoot -Parent
$runtimeRoot = Join-Path $projectRoot '.local-tools\ollama'
$ollamaExe = Join-Path $runtimeRoot 'ollama.exe'
if (-not (Test-Path -LiteralPath $ollamaExe)) {
    if (-not $Install) {
        throw 'Run .\scripts\start_ollama.ps1 -Install -PullModel once to download the free local runtime/model.'
    }
    New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
    $archive = Join-Path $runtimeRoot 'ollama-windows-amd64.zip'
    Invoke-WebRequest 'https://github.com/ollama/ollama/releases/download/v0.40.12/ollama-windows-amd64.zip' -OutFile $archive
    $expectedHash = '21814944f3e50d3f07b6bb3af75baddb96f59e91353c332ac9c5063b3bfd1041'
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant() -ne $expectedHash) {
        throw 'Official Ollama archive checksum mismatch. Archive was not executed.'
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $runtimeRoot -Force
}
# Settings affect only this helper and its child process, never the global machine.
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = Join-Path $projectRoot '.models\ollama'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_CONTEXT_LENGTH = [string]$ContextTokens
$env:OLLAMA_FLASH_ATTENTION = '1'
$env:OLLAMA_KV_CACHE_TYPE = 'q8_0'
$env:OLLAMA_NOPRUNE = '1'
# Installed llama-server --help exposes these inherited process-local cache bounds.
# Its defaults (32 recurrent checkpoints / 8192 MiB prompt cache) are too large here.
$env:LLAMA_ARG_CTX_CHECKPOINTS = '1'
$env:LLAMA_ARG_CACHE_RAM = '0'
$env:LLAMA_ARG_UBATCH = [string]$BatchTokens
try {
    $version = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
    Write-Output "Ollama already listening ($($version.version)); existing process settings were not changed."
} catch {
    $process = Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtimeRoot 'server.stdout.log') `
        -RedirectStandardError (Join-Path $runtimeRoot 'server.stderr.log')
    $process.Id | Set-Content (Join-Path $runtimeRoot 'server.pid')
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $ready) { throw "Ollama failed to start. See $runtimeRoot\server.stderr.log" }
    Write-Output "Local-only Ollama started (process $($process.Id))."
}
if ($PullModel) {
    & $ollamaExe pull $Model
    if ($LASTEXITCODE -ne 0) { throw 'Model download failed. Re-run with -PullModel to resume.' }
}
$downloaded = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5
if ($downloaded.models.name -contains $Model) {
    $modelInfo = Invoke-RestMethod 'http://127.0.0.1:11434/api/show' -Method Post `
        -ContentType 'application/json' -Body (@{ model = $Model } | ConvertTo-Json) -TimeoutSec 5
    if ($modelInfo.remote_host -or $modelInfo.remote_model -or $modelInfo.details.format -ne 'gguf') {
        throw 'Only downloaded local GGUF models are allowed.'
    }
    if ($NoWarmup) {
        Write-Output 'Downloaded local metadata verified; model warm-up deferred for resource profiling.'
        return
    }
    # A real short completion also warms GPU prompt processing before the bounded agent request.
    $warmupText = 'Reply only Ready. Warmup input: ' + (('warmup ' * 512) -join '')
    $warmup = @{
        model = $Model
        messages = @(@{ role = 'user'; content = $warmupText })
        stream = $false
        think = $false
        shift = $false
        truncate = $false
        keep_alive = '30m'
        options = @{ num_ctx = $ContextTokens; num_batch = $BatchTokens; num_predict = 8; temperature = 0 }
    } | ConvertTo-Json -Depth 5
    Invoke-RestMethod 'http://127.0.0.1:11434/api/chat' -Method Post `
        -ContentType 'application/json' -Body $warmup -TimeoutSec 180 | Out-Null
    Write-Output 'Local model loaded. Start OpsPilot Compose services on port 8001.'
} else {
    Write-Output 'Model is not downloaded. Re-run with -PullModel.'
}
