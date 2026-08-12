$ErrorActionPreference = 'Stop'
$PackageRoot = Split-Path -Parent $PSScriptRoot
python (Join-Path $PSScriptRoot 'verify_package.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
