<#
.SYNOPSIS
  Validate and upload every .github/skills/* folder to a Foundry project (safe to re-run).
.PARAMETER ProjectEndpoint
  Foundry project endpoint. Defaults to $env:FOUNDRY_PROJECT_ENDPOINT.
#>
param(
  [string]$ProjectEndpoint = $env:FOUNDRY_PROJECT_ENDPOINT,
  [string]$SkillsDir = (Join-Path $PSScriptRoot '..\.github\skills')
)
$ErrorActionPreference = 'Stop'
if (-not $ProjectEndpoint) { throw 'Set -ProjectEndpoint or FOUNDRY_PROJECT_ENDPOINT.' }

python (Join-Path $PSScriptRoot 'validate-skills.py') $SkillsDir
if ($LASTEXITCODE -ne 0) { throw 'Skill validation failed.' }

$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
$failed = @()
foreach ($dir in Get-ChildItem $SkillsDir -Directory) {
  Write-Host "Uploading $($dir.Name)"
  azd ai skill create $dir.Name --file $dir.FullName --force --project-endpoint $ProjectEndpoint --no-prompt | Out-Null
  if ($LASTEXITCODE -ne 0) { $failed += $dir.Name }
}
if ($failed) { throw "Failed: $($failed -join ', ')" }
azd ai skill list --project-endpoint $ProjectEndpoint
