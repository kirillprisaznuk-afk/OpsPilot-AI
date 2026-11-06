$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath '.env') {
    throw '.env already exists; preserving it. Edit it explicitly if needed.'
}
# Hex avoids URI escaping problems in the Compose connection URL.
$bytes = New-Object byte[] 24
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$rng.Dispose()
$passwordValue = [Convert]::ToHexString($bytes).ToLowerInvariant()
$content = "POSTGRES_PASSWORD=$passwordValue`nDATABASE_URL=postgresql+psycopg://opspilot:$passwordValue@127.0.0.1:55432/opspilot`n"
[System.IO.File]::WriteAllText((Join-Path $PWD '.env'), $content)
Write-Output 'Created ignored .env with a random local database password.'
