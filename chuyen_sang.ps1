# (c) 2026 BanhBaoChien AutoTool. Bao luu moi quyen.
# Chuyen tu 2 tool cu (FacebookUpStt + FacebookMonitor, cung thu muc cha) sang tool gop nay.
#   -Action chuyen : TAT (khong xoa) lich 2 tool cu -> doi luot dang chay xong -> chep du lieu -> cai + tao lich moi
#   -Action quaylai: xoa lich tool gop -> BAT lai lich 2 tool cu (du lieu tool cu khong bi dong toi)
param(
    [ValidateSet("chuyen", "quaylai")]
    [string]$Action = "chuyen"
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ToolDir = $PSScriptRoot
$Parent = Split-Path $ToolDir
$PostDir = Join-Path $Parent "FacebookUpStt"
$MonDir = Join-Path $Parent "FacebookMonitor"
$NewPrefix = "fb_tool_$(Split-Path $ToolDir -Leaf)__"

function Step($t) { Write-Host "`n>> $t" -ForegroundColor Cyan }
function Ok($t) { Write-Host "   OK: $t" -ForegroundColor Green }
function Fail($t) { Write-Host "`n   LOI: $t" -ForegroundColor Red; exit 1 }

function Old-Tasks {
    # Lich cua 2 tool cu nam o thu muc cha nay (khong dung lich cua ban sao tool o noi khac).
    Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
        ($_.TaskName -like "fb_dangbai_*" -or $_.TaskName -like "fb_monitor_*" -or $_.TaskName -like "fb_upstt_*") -and
        ($_.Actions | Where-Object { "$($_.Arguments)" -like "*$PostDir*" -or "$($_.Arguments)" -like "*$MonDir*" })
    }
}

function Test-LockBusy($lockPath) {
    try {
        $s = [IO.File]::Open($lockPath, "Open", "ReadWrite", "ReadWrite")
        try { $s.Lock(0, 1); $s.Unlock(0, 1); return $false } catch { return $true } finally { $s.Close() }
    } catch { return $false }
}

function Any-Busy {
    foreach ($lock in Get-ChildItem (Join-Path $PostDir "accounts\*\browser_profile.lock"), (Join-Path $MonDir "accounts\*\browser_profile.lock") -ErrorAction SilentlyContinue) {
        if (Test-LockBusy $lock.FullName) { return $true }
    }
    return [bool](@(Old-Tasks | Where-Object { $_.State -eq "Running" }).Count)
}

if ($Action -eq "quaylai") {
    Step "Xoa lich cua tool gop"
    Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "$NewPrefix*" } |
        ForEach-Object { Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false; Ok "Da xoa: $($_.TaskName)" }
    Step "Bat lai lich 2 tool cu"
    foreach ($t in @(Old-Tasks)) { Enable-ScheduledTask -TaskName $t.TaskName | Out-Null; Ok "Da bat: $($t.TaskName)" }
    Write-Host "`n   DA QUAY LAI 2 TOOL CU. Mo MO_TOOL.bat trong FacebookUpStt / FacebookMonitor nhu truoc." -ForegroundColor Green
    exit 0
}

if (-not (Test-Path (Join-Path $PostDir "config.json")) -or -not (Test-Path (Join-Path $MonDir "config.json"))) {
    Fail "Khong thay 2 tool cu o $PostDir va $MonDir"
}

Step "Tat lich 2 tool cu (khong xoa - chay QUAY_LAI_TOOL_CU.bat de bat lai)"
$old = @(Old-Tasks)
foreach ($t in $old) { Disable-ScheduledTask -TaskName $t.TaskName | Out-Null; Ok "Da tat: $($t.TaskName)" }
if (-not $old) { Ok "Khong co lich cu nao dang bat." }

Step "Doi cac luot dang chay cua tool cu xong (toi da 45 phut)"
$deadline = (Get-Date).AddMinutes(45)
while (Any-Busy) {
    if ((Get-Date) -gt $deadline) { Fail "Tool cu chay qua lau. Chay lai file nay sau." }
    Write-Host "   ... tool cu van dang chay, doi them ($(Get-Date -Format HH:mm:ss))"
    Start-Sleep -Seconds 20
}
Ok "Tool cu da ranh."

# Python (giong setup.ps1: bo qua ban gia cua Microsoft Store)
$python = $null
foreach ($cmd in "py", "python") {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($found -and $found.Source -notmatch "WindowsApps") { $python = $found.Source; break }
}
if (-not $python) {
    $python = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $python) { Fail "Khong thay Python. Chay CAI_DAT.bat cua tool cu truoc." }

if (Test-Path (Join-Path $ToolDir "config.json")) {
    Step "Tool gop da co du lieu -> bo qua buoc chep du lieu"
} else {
    Step "Chep du lieu 2 tool cu sang tool gop (tool cu giu nguyen)"
    $env:PYTHONUTF8 = "1"
    & $python (Join-Path $ToolDir "chuyen_du_lieu.py") $PostDir $MonDir
    if ($LASTEXITCODE -ne 0) { Fail "Chep du lieu bi loi (xem o tren). Lich cu dang tat: chay QUAY_LAI_TOOL_CU.bat de bat lai." }
}

Step "Cai dat + tao lich cho tool gop"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ToolDir "setup.ps1") -Action install
if ($LASTEXITCODE -ne 0) { Fail "Cai dat tool gop bi loi (xem o tren). Chay QUAY_LAI_TOOL_CU.bat de dung lai tool cu." }

Write-Host "`n   CHUYEN XONG. Tu nay mo tool bang MO_TOOL.bat trong thu muc FacebookTool." -ForegroundColor Green
Write-Host "   Lich 2 tool cu dang TAT (chua xoa). Muon quay lai: chay QUAY_LAI_TOOL_CU.bat." -ForegroundColor Green
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ToolDir "setup.ps1") -Action gui
