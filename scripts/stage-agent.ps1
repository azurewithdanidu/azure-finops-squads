[CmdletBinding()]
param()
# Copies finops_store and the JSON schemas into the agent package so the code deploy is self-contained.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$dest = Join-Path $root 'agents\finops-squad\src\finops_agent'
Remove-Item (Join-Path $dest 'finops_store'), (Join-Path $dest 'schemas') -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $root 'src\finops_store') $dest -Recurse -Exclude '__pycache__'
Copy-Item (Join-Path $root 'schemas') $dest -Recurse
foreach ($s in 'ledger.py', 'kpis.py') { Copy-Item (Join-Path $root "scripts\$s") $dest -Force }
Write-Host "Staged finops_store and schemas into $dest"
