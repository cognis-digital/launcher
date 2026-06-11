<#
.SYNOPSIS
  setup.ps1 — one-line bootstrap for the Cognis guided SETUP WIZARD (Windows).

.DESCRIPTION
  Run:
      .\setup.ps1
  ...and type a number. The wizard explains everything at your level (1-5).

  Launches cognis_setup.py (stdlib-only, no dependencies) pointed at a tool
  manifest:
    * a local MANIFEST.json if one sits next to this script, otherwise
    * the canonical cognis-arsenal MANIFEST.json fetched from GitHub (raw).
  If neither is reachable, the wizard still runs — fleet setup, configure,
  health-check and help all work without any manifest.

  Extra args pass straight through to the wizard, e.g.:
      .\setup.ps1 -ArgList '--dry-run'
#>
[CmdletBinding()]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]] $ArgList = @()
)

$ErrorActionPreference = 'Stop'
$scriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$wizard      = Join-Path $scriptDir 'cognis_setup.py'
$rawManifest = 'https://raw.githubusercontent.com/cognis-digital/cognis-arsenal/main/MANIFEST.json'

# --- locate a Python interpreter --------------------------------------------
$py = $null
foreach ($cand in @('C:\Python314\python.exe', 'python', 'python3', 'py')) {
  $cmd = Get-Command $cand -ErrorAction SilentlyContinue
  if ($cmd) { $py = $cmd.Source; break }
}
if (-not $py) {
  Write-Error 'Cognis setup needs Python 3. Install it, then re-run .\setup.ps1'
  exit 1
}
if (-not (Test-Path $wizard)) {
  Write-Error "cognis_setup.py not found next to setup.ps1 ($wizard)"
  exit 1
}

# --- if the caller already passed --manifest, don't second-guess them -------
if ($ArgList -contains '--manifest') {
  & $py $wizard @ArgList
  exit $LASTEXITCODE
}

# --- find a manifest: local first, then fetch the arsenal one ---------------
$manifest = $null
foreach ($cand in @(
    (Join-Path $scriptDir 'MANIFEST.json'),
    (Join-Path $scriptDir '..\_meta\cognis-arsenal\MANIFEST.json'))) {
  if (Test-Path $cand) { $manifest = (Resolve-Path $cand).Path; break }
}

$tmp = $null
if (-not $manifest) {
  $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("cognis-manifest.{0}.json" -f $PID)
  try {
    Invoke-WebRequest -Uri $rawManifest -OutFile $tmp -UseBasicParsing -ErrorAction Stop
    if ((Test-Path $tmp) -and ((Get-Item $tmp).Length -gt 0)) { $manifest = $tmp }
  } catch {
    Write-Host '  (couldn''t fetch the tool catalog — the wizard still runs:' -ForegroundColor Yellow
    Write-Host '   AI-fleet setup, configure, health-check and help all work.)' -ForegroundColor Yellow
  }
}

try {
  if ($manifest) {
    & $py $wizard '--manifest' $manifest @ArgList
  } else {
    & $py $wizard @ArgList
  }
  $code = $LASTEXITCODE
} finally {
  if ($tmp -and (Test-Path $tmp)) { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
}
exit $code
