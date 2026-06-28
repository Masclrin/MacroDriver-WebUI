try {
    $proc = Get-Process -Name "YuanShen" -ErrorAction Stop
    $proc.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::Realtime
    Write-Host "原神进程 (PID:$($proc.Id)) 优先级已设为: $($proc.PriorityClass)" -ForegroundColor Green
} catch {
    Write-Host "错误: 未找到原神进程，请先启动游戏" -ForegroundColor Red
}
Read-Host "按回车退出"