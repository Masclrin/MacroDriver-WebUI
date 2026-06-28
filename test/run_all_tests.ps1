# 自动化宏精度测试脚本
# 对每个预处理好的宏: 启动探针 → 执行宏 → 后分析

$ProjectRoot = "h:\宏驱动 webui 3.1"
$TestDir = Join-Path $ProjectRoot "test"
$ArtifactsDir = Join-Path $TestDir "artifacts"

$Tests = @(
    @{
        Name = "魔导火-大轮"
        Macro = "宏\RawInput_魔导火大轮.json"
        Timeline = "test\artifacts\expected_timeline_魔导火大轮.json"
        Events = 83
    },
    @{
        Name = "魔导火首轮"
        Macro = "宏\RawInput_魔导火首轮.json"
        Timeline = "test\artifacts\expected_timeline_魔导火首轮.json"
        Events = 83
    },
    @{
        Name = "魔导火-2轮aesz"
        Macro = "宏\RawInput_魔导火2轮aesz.json"
        Timeline = "test\artifacts\expected_timeline_魔导火2轮aesz.json"
        Events = 104
    },
    @{
        Name = "蒸火"
        Macro = "宏\RawInput_蒸火.json"
        Timeline = "test\artifacts\expected_timeline_蒸火.json"
        Events = 76
    }
)

$Results = @()

foreach ($Test in $Tests) {
    $Name = $Test.Name
    $MacroPath = Join-Path $ProjectRoot $Test.Macro
    $TimelinePath = Join-Path $ProjectRoot $Test.Timeline
    $CsvPath = Join-Path $ArtifactsDir "probe_result_$Name.csv"
    $LogPath = Join-Path $ArtifactsDir "probe_log_$Name.txt"
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "测试: $Name" -ForegroundColor Cyan
    Write-Host "  宏: $MacroPath" 
    Write-Host "  事件数: $($Test.Events)"
    Write-Host "========================================" -ForegroundColor Cyan
    
    # 先检查预期时间轴是否存在
    if (-not (Test-Path $TimelinePath)) {
        Write-Host "[错误] 预期时间轴不存在: $TimelinePath" -ForegroundColor Red
        continue
    }
    if (-not (Test-Path $MacroPath)) {
        Write-Host "[错误] 宏文件不存在: $MacroPath" -ForegroundColor Red
        continue
    }

    # 清理旧CSV
    if (Test-Path $CsvPath) { Remove-Item $CsvPath -Force }
    
    # 步骤1: 启动探针 (Background Job)
    Write-Host "[步骤1] 启动 RawInput 探针..." -ForegroundColor Yellow
    $ProbeJob = Start-Job -Name "Probe_$Name" -ScriptBlock {
        param($TestDir, $TimelinePath, $Events, $CsvPath)
        Set-Location $TestDir
        python "调试_RawInput探针.py" `
            --expected-timeline $TimelinePath `
            --filter-vk F13 `
            --events $Events `
            --timeout-sec 120 `
            --csv $CsvPath
    } -ArgumentList $TestDir, $TimelinePath, $Test.Events, $CsvPath
    
    # 等待探针启动
    Write-Host "[步骤2] 等待 4 秒让探针初始化..." -ForegroundColor Yellow
    Start-Sleep -Seconds 4
    
    # 检查探针是否还在运行
    $jobState = (Get-Job -Name "Probe_$Name").State
    if ($jobState -eq 'Failed') {
        $errorMsg = Receive-Job -Name "Probe_$Name"
        Write-Host "[错误] 探针启动失败: $errorMsg" -ForegroundColor Red
        Remove-Job -Name "Probe_$Name" -Force
        continue
    }
    
    # 步骤2: 运行宏
    Write-Host "[步骤3] 执行宏 (等待 $($Test.Events) 个事件, 约 18s)..." -ForegroundColor Yellow
    $MacroResult = python "运行测试宏.py" --macro $MacroPath --delay-before 1 2>&1
    Write-Host $MacroResult
    
    # 步骤3: 等待探针完成 (最长等待 60s)
    Write-Host "[步骤4] 等待探针完成..." -ForegroundColor Yellow
    $timeout = 60
    $elapsed = 0
    while ($elapsed -lt $timeout) {
        Start-Sleep -Seconds 1
        $jobState = (Get-Job -Name "Probe_$Name").State
        if ($jobState -eq 'Completed' -or $jobState -eq 'Failed' -or $jobState -eq 'Stopped') {
            break
        }
        $elapsed++
    }
    
    # 获取探针输出
    $ProbeOutput = Receive-Job -Name "Probe_$Name" -Wait -Timeout 10 2>&1
    $ProbeOutput | Out-File -FilePath $LogPath -Encoding utf8
    Remove-Job -Name "Probe_$Name" -Force
    
    Write-Host "[探针日志已保存: $LogPath]" -ForegroundColor Green
    
    # 检查CSV是否生成
    if (Test-Path $CsvPath) {
        Write-Host "[结果] CSV 已生成: $CsvPath" -ForegroundColor Green
        
        # 步骤4: 后分析
        Write-Host "[步骤5] 运行后分析..." -ForegroundColor Yellow
        $AnalysisResult = python "测试_真实宏时间线.py" --post-analyze $CsvPath --expected-timeline $TimelinePath 2>&1
        Write-Host $AnalysisResult
    } else {
        Write-Host "[警告] CSV 未生成!" -ForegroundColor Red
        # 输出探针日志的最后几行帮助诊断
        $ProbeOutput | Select-Object -Last 20
    }
    
    # 记录结果摘要
    $Results += @{
        Name = $Name
        CsvPath = $CsvPath
        LogPath = $LogPath
        ProbeOutput = $ProbeOutput
    }
    
    Write-Host "----------------------------------------" -ForegroundColor Gray
    Start-Sleep -Seconds 2
}

# 最终汇总
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "           全部测试完成" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
foreach ($r in $Results) {
    Write-Host "  $($r.Name): CSV=$($r.CsvPath), Log=$($r.LogPath)" -ForegroundColor White
}