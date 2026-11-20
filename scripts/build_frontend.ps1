# 构建前端并复制到后端静态目录
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
$static = Join-Path $root "semikb\static"

Set-Location $frontend
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    npm install
}
npm run build

New-Item -ItemType Directory -Force -Path $static | Out-Null
Copy-Item -Path (Join-Path $frontend "dist\*") -Destination $static -Recurse -Force
Write-Output "前端构建完成，已复制到 $static"
