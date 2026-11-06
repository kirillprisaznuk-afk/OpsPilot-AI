[CmdletBinding()]
param(
    [ValidateSet('Setup','Start','Stop','Status')][string]$Command = 'Start',
    [switch]$Build,
    [switch]$Open,
    [string]$Project = 'opspilot-stage1',
    [ValidateRange(1024,65535)][int]$WebPort = 3106,
    [ValidateRange(1024,65535)][int]$ApiPort = 8001,
    [ValidateRange(1024,65535)][int]$DbPort = 55432
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root '.env'
$accounts = Join-Path $root '.local-tools/stage5-demo/accounts.json'
$settings = @{}
$previous = @{}
Push-Location -LiteralPath $root
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install Docker Desktop with Compose.' }
    $configured = Test-Path -LiteralPath $envPath
    if ($Command -eq 'Setup') {
        if ($configured -or (Test-Path -LiteralPath $accounts)) {
            throw 'Local configuration or accounts already exist. Use Start or see Quick Start recovery.'
        }
        if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'Install uv before Setup.' }
    } else {
        if (-not $configured) { throw 'Run ./scripts/opspilot.ps1 Setup -Open for a fresh checkout.' }
        foreach ($line in Get-Content -LiteralPath $envPath -Encoding utf8) {
            if ($line -match '^([A-Z][A-Z0-9_]*)=([^\r\n]*)$') {
                $settings[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
            }
        }
        $Project = if ($settings['COMPOSE_PROJECT_NAME']) { $settings['COMPOSE_PROJECT_NAME'] } else { 'opspilot-stage1' }
        $WebPort = if ($settings['OPSPILOT_WEB_PORT']) { [int]$settings['OPSPILOT_WEB_PORT'] } else { 3106 }
        $ApiPort = if ($settings['OPSPILOT_API_PORT']) { [int]$settings['OPSPILOT_API_PORT'] } else { 8001 }
        $DbPort = if ($settings['OPSPILOT_DB_PORT']) { [int]$settings['OPSPILOT_DB_PORT'] } else { 55432 }
    }
    if ($Project -notmatch '^opspilot-[a-z0-9][a-z0-9_-]{0,42}$') { throw 'Invalid OpsPilot project name.' }
    $ports = @($WebPort, $ApiPort, $DbPort)
    if (@($ports | Select-Object -Unique).Count -ne 3 -or @($ports | Where-Object { $_ -lt 1024 -or $_ -gt 65535 }).Count) {
        throw 'Use three distinct loopback ports between 1024 and 65535.'
    }
    $web = "http://127.0.0.1:$WebPort"
    $api = "http://127.0.0.1:$ApiPort"
    docker version --format '{{.Server.Version}}' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        if ($Command -in 'Status','Stop') { throw 'Docker Engine is unavailable.' }
        docker desktop start --detach --timeout 20
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            docker version --format '{{.Server.Version}}' 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { break }
            Start-Sleep -Seconds 2
        }
        if ($LASTEXITCODE -ne 0) { throw 'Docker Engine is unavailable. Check Docker Desktop.' }
    }
    docker compose version --short | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose v2 is required.' }

    if ($Command -eq 'Setup') {
        $volumes = docker volume ls --format '{{.Name}}'
        if ($LASTEXITCODE -ne 0) { throw 'Could not inspect Docker volumes.' }
        $containers = docker ps -aq --filter "label=com.docker.compose.project=$Project"
        if ($LASTEXITCODE -ne 0) { throw 'Could not inspect Docker containers.' }
        if (($volumes | Where-Object { $_ -in "${Project}_opspilot_pgdata","${Project}_opspilot_frontend_sessions" }) -or $containers) {
            throw "Docker project '$Project' already has resources. Choose a new name and free ports for an isolated demo."
        }
        foreach ($port in $ports) {
            $probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $port)
            try { $probe.Start() } catch { throw "Local port $port is unavailable." } finally { $probe.Stop() }
        }
        $bytes = New-Object byte[] 24
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
        $password = [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
        $settings = @{
            COMPOSE_PROJECT_NAME = $Project
            OPSPILOT_WEB_PORT = "$WebPort"
            OPSPILOT_API_PORT = "$ApiPort"
            OPSPILOT_DB_PORT = "$DbPort"
            POSTGRES_PASSWORD = $password
            DATABASE_URL = "postgresql+psycopg://opspilot:$password@127.0.0.1:$DbPort/opspilot"
            LLM_PROVIDER = 'ollama'
            HYBRID_LLM_ENABLED = 'false'
            HYBRID_ALLOW_LEGACY = 'false'
        }
        $lines = $settings.Keys | Sort-Object | ForEach-Object { "$_=$($settings[$_])" }
        $file = [IO.File]::Open($envPath, 'CreateNew', 'Write', 'None')
        try {
            $writer = [IO.StreamWriter]::new($file, [Text.UTF8Encoding]::new($false))
            try { $writer.WriteLine(($lines -join [Environment]::NewLine)) } finally { $writer.Dispose() }
        } finally { $file.Dispose() }
    }

    # Keep Compose and Python bound to the same checkout even with inherited shell settings.
    foreach ($key in @('COMPOSE_PROJECT_NAME','OPSPILOT_WEB_PORT','OPSPILOT_API_PORT','OPSPILOT_DB_PORT',
                       'POSTGRES_PASSWORD','DATABASE_URL','WORKFLOW_DB_USER','WORKFLOW_DB_PASSWORD',
                       'WORKFLOW_DATABASE_URL','OPENAI_API_KEY','HYBRID_LLM_ENABLED','LLM_PROVIDER',
                       'HYBRID_ALLOW_LEGACY','PYTHONPATH','EMBEDDING_CACHE')) {
        $previous[$key] = (Get-Item -LiteralPath "Env:$key" -ErrorAction SilentlyContinue).Value
        if ($settings.ContainsKey($key)) { [Environment]::SetEnvironmentVariable($key, $settings[$key], 'Process') }
        else { Remove-Item -LiteralPath "Env:$key" -ErrorAction SilentlyContinue }
    }
    $env:PYTHONPATH = "backend$([IO.Path]::PathSeparator)."
    $env:EMBEDDING_CACHE = Join-Path $root '.models/minilm'
    $compose = @('compose','--project-directory',$root,'--env-file',$envPath,'--project-name',$Project,
                 '-f',(Join-Path $root 'docker-compose.yml'))
    function Invoke-Compose {
        docker @compose @args
        if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed for project '$Project'." }
    }
    function Invoke-SetupPython {
        uv run --frozen --no-dev python @args
        if ($LASTEXITCODE -ne 0) { throw 'Local setup stopped. See Quick Start for safe recovery.' }
    }
    Invoke-Compose config --quiet
    if ($Command -eq 'Setup') {
        uv sync --frozen --no-dev
        if ($LASTEXITCODE -ne 0) { throw 'Locked Python dependency installation failed.' }
        Invoke-SetupPython -m scripts.knowledge download-model
        Invoke-Compose up -d --wait --wait-timeout 90 db
        Invoke-SetupPython -m alembic upgrade head
        Invoke-SetupPython -m scripts.manage seed
        Invoke-SetupPython -m scripts.knowledge index
        Invoke-SetupPython -m scripts.bootstrap_workflow
        $Build = $true
    }
    if ($Command -eq 'Stop') {
        Invoke-Compose stop frontend api db
        Write-Output "Stopped only $Project. Database and session volumes retained."
        return
    }
    if ($Command -eq 'Status') {
        Write-Output "Frontend: $web"
        Write-Output "API: $api"
        Invoke-Compose ps --all --format '{{.Service}} {{.State}} {{.Health}}'
        foreach ($endpoint in @(@('Database/API','/ready'),@('Knowledge','/api/v1/knowledge/status'),@('Intelligence','/api/v1/hybrid/status'))) {
            try {
                $result = Invoke-RestMethod ($api + $endpoint[1]) -TimeoutSec 4
                if ($endpoint[0] -eq 'Knowledge') { Write-Output "Knowledge: $($result.documents) documents, $($result.chunks) chunks" }
                else { Write-Output "$($endpoint[0]): available" }
            } catch { Write-Output "$($endpoint[0]): unavailable" }
        }
        docker @compose exec -T api /code/.venv/bin/python -m scripts.workflow_status 2>$null
        if ($LASTEXITCODE -ne 0) { Write-Output 'Workflow: unavailable' }
        try {
            $null = Invoke-WebRequest "$web/login" -UseBasicParsing -TimeoutSec 4
            Write-Output 'Browser sign-in: available'
        } catch { Write-Output 'Browser sign-in: unavailable' }
        try {
            $model = Invoke-RestMethod 'http://127.0.0.1:11434/api/ps' -TimeoutSec 2
            Write-Output "Experimental Ollama: reachable, $(@($model.models).Count) resident models"
        } catch { Write-Output 'Experimental Ollama: unavailable; deterministic mode needs no model' }
        return
    }
    if (-not (Test-Path -LiteralPath $accounts) -or
        (Get-Content -LiteralPath $envPath -Raw -Encoding utf8) -notmatch '(?m)^WORKFLOW_DB_PASSWORD=\S+') {
        throw 'Local demo accounts or restricted database credentials are missing. See Quick Start recovery.'
    }
    $flags = @('up','-d','--wait','--wait-timeout','150')
    if ($Build) { $flags += '--build' }
    Invoke-Compose @flags db api frontend
    $ready = Invoke-RestMethod "$api/ready" -TimeoutSec 8
    $knowledge = Invoke-RestMethod "$api/api/v1/knowledge/status" -TimeoutSec 10
    $signIn = Invoke-WebRequest "$web/login" -UseBasicParsing -TimeoutSec 8
    if ($ready.status -ne 'ready' -or $knowledge.documents -ne 44 -or $signIn.StatusCode -ne 200) {
        throw 'Database, knowledge or sign-in readiness failed. Run Status.'
    }
    Write-Output "OpsPilot ready: $web"
    if ($Command -eq 'Setup') { Write-Output "Local demo accounts: $accounts" }
    if ($Open) { Start-Process "$web/login" }
} finally {
    foreach ($key in $previous.Keys) {
        if ($null -eq $previous[$key]) { Remove-Item -LiteralPath "Env:$key" -ErrorAction SilentlyContinue }
        else { [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process') }
    }
    Pop-Location
}
