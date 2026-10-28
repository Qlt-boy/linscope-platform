# 启动「林鉴知微平台 | LinScopePlatform」后端（FastAPI + 前端静态站点同进程）
#   .\start.ps1                # 前台启动，Ctrl+C 退出（默认 127.0.0.1:1314）
#   .\start.ps1 -Port 1314 -Host 0.0.0.0
#   .\start.ps1 -Background    # 后台启动，日志写 data\server.out.log
param(
  [int]$Port = 1314,
  [string]$HostName = "127.0.0.1",
  [switch]$Background
)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venv = Join-Path $root ".venv"
$py = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $py)) {
  Write-Host "未发现虚拟环境，正在创建并安装依赖…"
  python -m venv $venv
  & $py -m pip install -q --upgrade pip
  & $py -m pip install -q -r (Join-Path $root "requirements.txt")
}

if (-not (Test-Path (Join-Path $root ".env"))) {
  Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env")
  Write-Host "已按 .env.example 生成 .env（纯本地采集，无需外部平台配置）。"
}

if ($Background) {
  New-Item -ItemType Directory -Force -Path (Join-Path $root "data") | Out-Null
  Start-Process -FilePath $py -ArgumentList "run.py","--host",$HostName,"--port",$Port `
    -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $root "data\server.out.log") `
    -RedirectStandardError  (Join-Path $root "data\server.err.log")
  Start-Sleep -Seconds 4
  Write-Host "后端已在后台启动： http://${HostName}:$Port/  （日志：data\server.out.log）"
} else {
  & $py run.py --host $HostName --port $Port
}