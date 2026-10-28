# 停止后台运行的后端（按监听端口找进程）
param([int]$Port = 1314)
$lines = netstat -ano | Select-String ":$Port\s+.*LISTENING"
$pids = @()
foreach ($l in $lines) {
  $parts = ($l -split "\s+") | Where-Object { $_ }
  if ($parts.Length -ge 5) { $pids += [int]$parts[-1] }
}
$pids = $pids | Sort-Object -Unique
if (-not $pids) { Write-Host "端口 $Port 上没有监听进程"; exit 0 }
foreach ($procId in $pids) {
  Write-Host "停止进程 $procId"
  Stop-Process -Id $procId -Force
}
Write-Host "已停止。"