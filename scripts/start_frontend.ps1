[CmdletBinding()]
param([switch]$Build, [switch]$Open)
& (Join-Path $PSScriptRoot 'opspilot.ps1') Start -Build:$Build -Open:$Open
