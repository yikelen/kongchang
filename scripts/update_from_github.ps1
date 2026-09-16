# 从 GitHub 拉最新源码。不碰 vendor（Python/mpv）和 data（工程/设置）。
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path (Join-Path $Root ".git"))) {
    Write-Host "本文件夹不是 git 仓库，无法 git pull。"
    Write-Host "请到 https://github.com/yikelen/kongchang/releases/latest 下载便携 zip，"
    Write-Host "解压后把旧目录的 data 和工程 json 拷过去。"
    exit 2
}

$git = Get-Command git -ErrorAction SilentlyContinue
if ($null -eq $git) {
    Write-Host "找不到 git。请先安装 Git for Windows，或改下 Release zip。"
    exit 2
}

Write-Host "远程："
git remote -v
Write-Host ""
git fetch origin
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$local = (git rev-parse HEAD).Trim()
$remote = (git rev-parse origin/main).Trim()
Write-Host "本地  $local"
Write-Host "GitHub origin/main  $remote"
if ($local -eq $remote) {
    Write-Host "已经是最新。"
    exit 0
}

$dirty = git status --porcelain
if ($dirty) {
    Write-Host ""
    Write-Host "工作区有未提交改动，为避免覆盖，没有自动 pull。"
    Write-Host "请先自己处理（提交或备份），再运行： git pull origin main"
    git status -sb
    exit 3
}

git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host ""
Write-Host "源码已更新。vendor 和 data 未改。请重新打开「启动.bat」。"
