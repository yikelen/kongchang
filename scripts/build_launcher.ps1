param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
    throw 'Windows .NET Framework C# 编译器不存在，无法生成启动器。'
}
$output = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $output | Out-Null
$exe = Join-Path $output '简易控场.exe'
$source = Join-Path $PSScriptRoot 'windows_launcher.cs'
$icon = Join-Path $repoRoot 'assets\app_v3.ico'
& $compiler /nologo /codepage:65001 /target:winexe /platform:anycpu /reference:System.Windows.Forms.dll "/win32icon:$icon" "/out:$exe" $source
if ($LASTEXITCODE -ne 0) { throw "启动器编译失败（$LASTEXITCODE）。" }
Write-Output $exe
