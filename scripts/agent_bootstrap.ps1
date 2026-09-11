#Requires -Version 5.1
<#
.SYNOPSIS
  Agent / 自动化用：下载 vendor\python 与 vendor\mpv（无 pause）。
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\agent_bootstrap.ps1
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Test-BootstrapPython {
    param([string[]]$Invoke)
    try {
        & $Invoke[0] $Invoke[1..($Invoke.Length - 1)] -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

$candidates = @(
    @("py", "-3"),
    @("python")
)
$pyInvoke = $null
foreach ($c in $candidates) {
    if (Test-BootstrapPython -Invoke $c) {
        $pyInvoke = $c
        break
    }
}
if (-not $pyInvoke) {
    throw "Need Python 3.11+ on PATH (py -3 or python) to bootstrap portable runtime."
}

Write-Host "Bootstrap Python:" ($pyInvoke -join " ")

function Invoke-PyScript([string]$RelScript) {
    $script = Join-Path $Root $RelScript
    if ($pyInvoke.Length -eq 1) {
        & $pyInvoke[0] $script
    } else {
        & $pyInvoke[0] $pyInvoke[1] $script
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Failed: $RelScript (exit $LASTEXITCODE)"
    }
}

Write-Host "[1/2] scripts\setup_portable_python.py"
Invoke-PyScript "scripts\setup_portable_python.py"

Write-Host "[2/2] scripts\download_mpv.py"
Invoke-PyScript "scripts\download_mpv.py"

foreach ($rel in @("vendor\python\pythonw.exe", "vendor\mpv\mpv.exe")) {
    $p = Join-Path $Root $rel
    if (-not (Test-Path $p)) { throw "Missing after bootstrap: $rel" }
    Write-Host "OK $rel"
}

Write-Host "Bootstrap done. Start with: .\启动.bat"
exit 0
