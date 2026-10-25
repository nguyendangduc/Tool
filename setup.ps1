# (c) 2026 BanhBaoChien AutoTool. Bao luu moi quyen. Nghiem cam sao chep, chia se, ban lai.
# Cai dat / dang nhap / tao lich cho tool Facebook. Duoc goi tu cac file .bat.
# File nay GIONG HET NHAU o ca 3 tool; tu nhan biet tool theo file .py trong thu muc.
#   -Action install  : cai Python + Playwright + Chromium, cap nhat lich (dang nhap / cau hinh lam trong giao dien)
#   -Action config   : mo giao dien sua cau hinh va cho dong (dung khi cai dat)
#   -Action gui      : mo giao dien, khong cho (MO_TOOL.bat)
#   -Action login    : mo cua so dang nhap Facebook
#   -Action schedule : tao lai lich theo config
#   -Action remove   : xoa lich
param(
    [ValidateSet("install", "gui", "config", "login", "schedule", "remove")]
    [string]$Action = "install"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$script:PythonExe = $null
$ToolDir = $PSScriptRoot
$FolderName = Split-Path $ToolDir -Leaf

# Ma thoat cua file .py (xem fb_login.py)
$EXIT_NOT_LOGGED_IN = 3
$EXIT_PROFILE_BUSY = 4

function Script-Path($name) {
    # File .py, hoac .pyc neu ban gui khach da bo .py (xem dong_goi.ps1).
    $py = Join-Path $ToolDir "$name.py"
    if (Test-Path $py) { return $py }
    return Join-Path $ToolDir "$name.pyc"
}

if ((Test-Path (Join-Path $ToolDir "tool_store.py")) -or (Test-Path (Join-Path $ToolDir "tool_store.pyc"))) {
    # Tool gop: dang bai (moi noi dung 1 lich theo gio) + theo doi (moi tai khoan 1 lich lap lai), 1 config.json.
    # main.py chuyen lenh sang fb_upstt.py / fb_monitor_v4.py.
    $Tool = @{
        Kind       = "gop"
        Multi      = $true
        Script     = Script-Path "main"
        Config     = Join-Path $ToolDir "config.json"
        TaskName   = "fb_tool_$FolderName"
        TaskPrefix = "fb_tool_${FolderName}__"
    }
} elseif (Test-Path (Join-Path $ToolDir "monitor_store.py")) {
    # Monitor ban moi: nhieu tai khoan / nhom theo doi (config.json), moi tai khoan 1 lich quet.
    $Tool = @{
        Kind       = "giamsat"
        Multi      = $true
        Script     = Join-Path $ToolDir "fb_monitor_v4.py"
        Config     = Join-Path $ToolDir "config.json"
        TaskName   = "fb_monitor_$FolderName"
        TaskPrefix = "fb_monitor_${FolderName}__"
    }
} elseif (Test-Path (Join-Path $ToolDir "fb_monitor_v4.py")) {
    $Tool = @{
        Kind     = "monitor"
        Script   = Join-Path $ToolDir "fb_monitor_v4.py"
        Config   = Join-Path $ToolDir "fb_monitor_config.txt"
        TaskName = "fb_monitor_$FolderName"
    }
} elseif (Test-Path (Join-Path $ToolDir "upstt_store.py")) {
    # Tool dang bai ban moi: nhieu tai khoan / nhom noi dung (config.json), moi nhom noi dung 1 lich.
    $Tool = @{
        Kind       = "dangbai"
        Multi      = $true
        Script     = Join-Path $ToolDir "fb_upstt.py"
        Config     = Join-Path $ToolDir "config.json"
        TaskName   = "fb_upstt_$FolderName"
        TaskPrefix = "fb_dangbai_${FolderName}__"
    }
} elseif (Test-Path (Join-Path $ToolDir "fb_upstt.py")) {
    $Tool = @{
        Kind     = "upstt"
        Script   = Join-Path $ToolDir "fb_upstt.py"
        Config   = Join-Path $ToolDir "fb_upstt_config.txt"
        TaskName = "fb_upstt_$FolderName"
    }
} else {
    Write-Host "LOI: Khong thay fb_monitor_v4.py hoac fb_upstt.py trong $ToolDir" -ForegroundColor Red
    exit 1
}

function Step($text) { Write-Host "`n>> $text" -ForegroundColor Cyan }
function Ok($text) { Write-Host "   OK: $text" -ForegroundColor Green }
function Fail($text) { Write-Host "`n   LOI: $text" -ForegroundColor Red; exit 1 }

# ------------------------------------------------------------------ config
function Read-Config {
    if ($Tool.Multi) { return @{} }  # config.json do fb_upstt.py tu kiem tra
    if (-not (Test-Path $Tool.Config)) { Fail "Khong thay file $($Tool.Config)" }
    $config = @{}
    foreach ($raw in Get-Content $Tool.Config -Encoding UTF8) {
        $line = $raw.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { continue }
        $key, $value = $line.Split("=", 2)
        $config[$key.Trim()] = $value.Trim()
    }
    return $config
}

function Get-ScheduleTimes($config) {
    $times = @($config["SCHEDULE_TIMES"] -split "\|" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if (-not $times) { Fail "SCHEDULE_TIMES trong config dang trong." }
    foreach ($t in $times) {
        if ($t -notmatch "^([01]\d|2[0-3]):[0-5]\d$") {
            Fail "Gio '$t' trong SCHEDULE_TIMES sai dinh dang. Dung HH:MM, vi du 06:30|19:00"
        }
    }
    return $times | Sort-Object -Unique
}

function Get-Minutes($config, $key, $default) {
    $raw = $config[$key]
    if (-not $raw) { return $default }
    $value = 0
    if (-not [int]::TryParse($raw, [ref]$value) -or $value -lt 1 -or $value -gt 1440) {
        Fail "$key phai la so phut tu 1 den 1440 (dang la '$raw')."
    }
    return $value
}

function Get-ConfigProblem($config) {
    # Tra ve mo ta loi dau tien, hoac $null neu config du.
    if ($Tool.Multi) {
        $out = Invoke-ToolOutput @("--validate")
        if ($LASTEXITCODE -ne 0) { return (@($out) -join " | ") }
        return $null
    }
    if ($Tool.Kind -eq "monitor") {
        if (-not ($config["GROUP_URLS"] -or $config["GROUP_URL"])) { return "Chua dien nhom Facebook can theo doi." }
        if (-not $config["TELEGRAM_TOKEN"]) { return "Chua dien Telegram Token." }
        if (-not $config["TELEGRAM_CHAT_ID"]) { return "Chua dien Telegram Chat ID." }
        $every = 40; $max = 20
        if ($config["RUN_EVERY_MINUTES"] -and -not [int]::TryParse($config["RUN_EVERY_MINUTES"], [ref]$every)) { return "So phut giua 2 lan quet khong hop le." }
        if ($config["MAX_RUN_MINUTES"] -and -not [int]::TryParse($config["MAX_RUN_MINUTES"], [ref]$max)) { return "So phut toi da moi lan quet khong hop le." }
        if ($max -ge $every) { return "Thoi gian toi da moi lan quet ($max) phai nho hon so phut giua 2 lan quet ($every)." }
    } else {
        if (-not $config["GROUP_URLS"]) { return "Chua dien nhom Facebook can dang." }
        if (-not $config["SHARE_URL"]) { return "Chua dien noi dung / link bai can chia se." }
        $times = @($config["SCHEDULE_TIMES"] -split "\|" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
        if (-not $times) { return "Chua dien gio dang." }
        foreach ($t in $times) { if ($t -notmatch "^([01]\d|2[0-3]):[0-5]\d$") { return "Gio dang '$t' sai dinh dang (dung HH:MM)." } }
    }
    return $null
}

function Test-Config($config) {
    $problem = Get-ConfigProblem $config
    if ($problem) { Fail "$problem Mo MO_TOOL.bat de sua cau hinh." }
    Ok "Config day du."
}

function Open-ConfigGui($python) {
    Step "Mo cua so cau hinh (dien xong bam Luu roi dong cua so)"
    $env:PYTHONUTF8 = "1"
    $gui = Script-Path "cau_hinh"
    $null = Start-Process -FilePath $python -ArgumentList "`"$gui`"" -WorkingDirectory $ToolDir -NoNewWindow -Wait -PassThru
}

function Ensure-Config($python) {
    Step "Kiem tra cau hinh"
    $problem = Get-ConfigProblem (Read-Config)
    if (-not $problem) { Ok "Config day du."; return }
    Write-Host "   $problem -> mo cua so cau hinh de dien." -ForegroundColor Yellow
    Open-ConfigGui $python
    Test-Config (Read-Config)
}

# ------------------------------------------------------------------ python
function Find-Python {
    # Bo qua ban "python" gia cua Microsoft Store (nam trong WindowsApps).
    $candidates = @()
    foreach ($cmd in "py", "python") {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found -and $found.Source -notmatch "WindowsApps") { $candidates += $found.Source }
    }
    $candidates += Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | ForEach-Object FullName

    foreach ($exe in $candidates) {
        try {
            $path = & $exe -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $path -and (Test-Path $path)) { return $path.Trim() }
        } catch {}
    }
    return $null
}

function Install-Python {
    Step "Kiem tra Python"
    $python = Find-Python
    if ($python) { Ok $python; $script:PythonExe = $python; return $python }

    Write-Host "   Chua co Python -> dang cai (mat vai phut)..."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Fail "May khong co winget. Hay cai Python tu https://www.python.org/downloads/ (tick 'Add python.exe to PATH') roi chay lai file nay."
    }
    winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    $python = Find-Python
    if (-not $python) { Fail "Cai Python khong thanh cong. Hay cai tay tu https://www.python.org/downloads/ roi chay lai." }
    Ok $python
    $script:PythonExe = $python
    return $python
}

function Install-Playwright($python) {
    Step "Cai thu vien can thiet"
    $req = Join-Path $ToolDir "requirements.txt"
    if (Test-Path $req) {
        & $python -m pip install --quiet -r $req
    } else {
        # Du phong neu thieu requirements.txt (vd ban cu).
        & $python -m pip install --quiet playwright sv-ttk requests cryptography
    }
    if ($LASTEXITCODE -ne 0) { Fail "Cai thu vien that bai (kiem tra mang Internet)." }
    # Kiem tra import duoc that su (tranh loi 'thieu requests' khi chep sang may khac).
    $env:PYTHONUTF8 = "1"
    & $python -c "import playwright, sv_ttk, requests, cryptography" 2>$null
    if ($LASTEXITCODE -ne 0) { Fail "Thu vien cai xong nhung chua import duoc. Thu chay lai CAI_DAT.bat." }
    Ok "playwright, sv-ttk, requests, cryptography"

    Step "Cai trinh duyet Chromium cho Playwright"
    & $python -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { Fail "Cai Chromium that bai (kiem tra mang Internet)." }
    Ok "Chromium"
}

function Require-Python {
    $python = Find-Python
    if (-not $python) { Fail "Chua cai dat. Chay CAI_DAT.bat truoc." }
    $script:PythonExe = $python
    return $python
}

function Invoke-ToolOutput($toolArgs) {
    # Chay fb_upstt.py va lay noi dung in ra (dung cho --validate, --accounts, --schedule-json).
    $env:PYTHONUTF8 = "1"
    Push-Location $ToolDir
    try { $out = & $script:PythonExe $Tool.Script @toolArgs 2>&1 | ForEach-Object { "$_" } }
    finally { Pop-Location }
    return $out
}

function Get-Accounts {
    # [{Id, Name}] cac tai khoan co noi dung dang bat.
    $list = @()
    foreach ($line in @(Invoke-ToolOutput @("--accounts"))) {
        $parts = "$line".Split("`t", 2)
        if ($parts.Count -eq 2) { $list += [pscustomobject]@{ Id = $parts[0]; Name = $parts[1] } }
    }
    return $list
}

# ------------------------------------------------------------------ login
function Invoke-Tool($python, $mode) {
    # In thang ra cua so (khong qua pipe) va lay ma thoat.
    $env:PYTHONUTF8 = "1"
    $process = Start-Process -FilePath $python -ArgumentList "`"$($Tool.Script)`" $mode" `
        -WorkingDirectory $ToolDir -NoNewWindow -Wait -PassThru
    return $process.ExitCode
}

function Test-LockBusy($lockPath) {
    # fb_login.py khoa 1 byte cua browser_profile.lock khi tool dang chay.
    if (-not (Test-Path $lockPath)) { return $false }
    try {
        $stream = [IO.File]::Open($lockPath, "Open", "ReadWrite", "ReadWrite")
        try { $stream.Lock(0, 1); $stream.Unlock(0, 1); return $false }
        catch { return $true }
        finally { $stream.Close() }
    } catch { return $true }
}

function Test-ToolBusy($accountId) {
    if ($Tool.Multi) {
        $pattern = if ($accountId) { $accountId } else { "*" }
        $locks = Join-Path $ToolDir (Join-Path "accounts" (Join-Path $pattern "browser_profile.lock"))
        foreach ($lock in Get-ChildItem $locks -ErrorAction SilentlyContinue) {
            if (Test-LockBusy $lock.FullName) { return $true }
        }
        return $false
    }
    return Test-LockBusy (Join-Path $ToolDir "browser_profile.lock")
}

function Wait-ToolIdle($maxMinutes, $accountId) {
    if (-not (Test-ToolBusy $accountId)) { return }
    Write-Host "   Tool dang chay theo lich -> tu dong doi tool chay xong (toi da $maxMinutes phut)." -ForegroundColor Yellow
    Write-Host "   Cu de yen cua so nay. Muon huy thi dong cua so." -ForegroundColor Yellow
    $deadline = (Get-Date).AddMinutes($maxMinutes)
    while (Test-ToolBusy $accountId) {
        if ((Get-Date) -gt $deadline) { Fail "Tool chay qua lau. Thu lai sau." }
        Write-Host "   ... van dang chay, doi them ($(Get-Date -Format HH:mm:ss))"
        Start-Sleep -Seconds 30
    }
    Ok "Tool da chay xong."
}

function Select-Account {
    $accounts = @(Get-Accounts)
    if (-not $accounts) { Fail "Chua co tai khoan nao. Mo MO_TOOL.bat de them tai khoan." }
    if ($accounts.Count -eq 1) { return $accounts[0] }
    Write-Host ""
    for ($i = 0; $i -lt $accounts.Count; $i++) { Write-Host "   [$($i + 1)] $($accounts[$i].Name)" }
    $pick = Read-Host "   Chon tai khoan (go so)"
    $n = 0
    if (-not [int]::TryParse($pick, [ref]$n) -or $n -lt 1 -or $n -gt $accounts.Count) { Fail "Chon khong hop le." }
    return $accounts[$n - 1]
}

function Open-Login($python, $account) {
    if ($Tool.Multi) {
        if (-not $account) { $account = Select-Account }
        Step "Mo cua so dang nhap Facebook cho: $($account.Name)"
        Wait-ToolIdle 45 $account.Id
        $code = Invoke-Tool $python "--login --account $($account.Id)"
        # Khong dung ca cai dat: bao loi roi lam tiep tai khoan khac (tai khoan nay tam dung, khong co lich).
        if ($code -eq $EXIT_PROFILE_BUSY) {
            Write-Host "   CANH BAO: '$($account.Name)' dang chay theo lich. Dang nhap lai sau trong MO_TOOL.bat." -ForegroundColor Yellow
            return
        }
        if ($code -ne 0) {
            Write-Host "   CANH BAO: '$($account.Name)' chua dang nhap duoc -> tai khoan nay TAM DUNG." -ForegroundColor Yellow
            Write-Host "   Dang nhap lai sau: mo MO_TOOL.bat, chon tai khoan, bam 'Dang nhap'." -ForegroundColor Yellow
            return
        }
        Ok "Da dang nhap: $($account.Name)"
        return
    }
    Step "Mo cua so dang nhap Facebook"
    Wait-ToolIdle 30
    $code = Invoke-Tool $python "--login"
    if ($code -eq $EXIT_PROFILE_BUSY) { Fail "Tool dang chay theo lich. Doi vai phut roi bam lai." }
    if ($code -ne 0) { Fail "Chua dang nhap duoc Facebook. Chay lai CAI_DAT.bat de thu lai." }
    Ok "Da dang nhap Facebook."
}

function Ensure-Login($python) {
    if ($Tool.Multi) {
        foreach ($account in @(Get-Accounts)) {
            Step "Kiem tra dang nhap: $($account.Name)"
            $code = Invoke-Tool $python "--check --account $($account.Id)"
            if ($code -eq 0) { Ok "Dang dang nhap."; continue }
            if ($code -eq $EXIT_PROFILE_BUSY) {
                Write-Host "   Tai khoan dang dang bai -> bo qua kiem tra." -ForegroundColor Yellow
                continue
            }
            if ($code -ne $EXIT_NOT_LOGGED_IN) {
                Write-Host "   CANH BAO: kiem tra dang nhap '$($account.Name)' bi loi (xem o tren) -> thu dang nhap." -ForegroundColor Yellow
            }
            Open-Login $python $account
        }
        return
    }
    Step "Kiem tra dang nhap Facebook (khong dang bai, khong comment)"
    $code = Invoke-Tool $python "--check"
    if ($code -eq 0) { Ok "Dang dang nhap."; return }
    if ($code -eq $EXIT_PROFILE_BUSY) {
        # Tool dang chay = da cai va dang nhap tu truoc -> bo qua, van tao lich.
        Write-Host "   Tool dang chay theo lich -> bo qua kiem tra dang nhap." -ForegroundColor Yellow
        return
    }
    if ($code -ne $EXIT_NOT_LOGGED_IN) { Fail "Kiem tra dang nhap bi loi (xem thong bao o tren)." }
    Open-Login $python
}

# ------------------------------------------------------------------ schedule
function New-TaskSettings($limit) {
    # -WakeToRun: may dang ngu (Sleep) thi Windows tu danh thuc de chay tool.
    return New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -WakeToRun `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit $limit
}

function Register-Multi($python) {
    # Dung chung cho tool dang bai (lich theo gio, moi nhom noi dung 1 lich)
    # va Monitor (lich lap lai, moi tai khoan 1 lich).
    Test-Config (Read-Config)
    $pythonw = Join-Path (Split-Path $python) "pythonw.exe"
    if (-not (Test-Path $pythonw)) { $pythonw = $python }
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

    # Truyen JSON lam tham so (khong qua pipe) de PowerShell 5.1 tra ve tung phan tu, khong gop thanh 1.
    # Chi lay dong JSON (bat dau bang "["), bo qua moi dong khac lo in ra.
    $json = @(Invoke-ToolOutput @("--schedule-json")) | Where-Object { "$_".TrimStart().StartsWith("[") } | Select-Object -Last 1
    if (-not $json) { Fail "Khong doc duoc danh sach lich tu tool." }
    $entries = @(ConvertFrom-Json $json)
    if ($entries.Count -eq 1 -and $entries[0] -is [array]) { $entries = $entries[0] }
    $keep = @()
    foreach ($e in $entries) {
        $name = "$($Tool.TaskPrefix)$($e.task)"
        $keep += $name
        $action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$($Tool.Script)`" $($e.args)" -WorkingDirectory $ToolDir
        if ($e.times) {
            $dayNames = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
            $days = @($e.weekdays | ForEach-Object { $dayNames[[int]$_] })
            if ($days -and $days.Count -lt 7) {
                Step "Tao lich '$($e.name)' $($days -join ',') luc: $(@($e.times) -join ', ')"
                $triggers = foreach ($t in @($e.times)) {
                    New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At $t
                }
            } else {
                Step "Tao lich '$($e.name)' hang ngay luc: $(@($e.times) -join ', ')"
                $triggers = foreach ($t in @($e.times)) { New-ScheduledTaskTrigger -Daily -At $t }
            }
            # Cho xep hang toi da 40 phut + dang bai -> gioi han 3 tieng.
            $settings = New-TaskSettings (New-TimeSpan -Hours 3)
        } else {
            Step "Tao lich '$($e.name)': quet moi $($e.every) phut, toi da $($e.max) phut/lan"
            $triggers = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes([int]$e.offset) `
                -RepetitionInterval (New-TimeSpan -Minutes ([int]$e.every))
            # Tool tu dung sau max phut; qua them 10 phut thi Windows tat han.
            $settings = New-TaskSettings (New-TimeSpan -Minutes ([int]$e.max + 10))
        }
        try {
            $null = Register-ScheduledTask -TaskName $name -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Force
        } catch {
            Fail "Khong tao duoc lich: $($_.Exception.Message) Hay chay bang file .bat va bam 'Yes' khi Windows hoi quyen."
        }
        Ok "Da tao."
    }

    # Xoa lich cua muc da xoa / da tat, va lich kieu cu (1 lich cho ca tool).
    foreach ($task in Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
        ($_.TaskName -like "$($Tool.TaskPrefix)*" -and $keep -notcontains $_.TaskName) -or $_.TaskName -eq $Tool.TaskName }) {
        Unregister-ScheduledTask -TaskName $task.TaskName -Confirm:$false
        Ok "Da xoa lich cu: $($task.TaskName)"
    }
    if (-not $entries) { Write-Host "   Chua co lich: chua co tai khoan nao dang nhap, hoac chua bat muc nao, hoac dang Tam dung toan bo." -ForegroundColor Yellow }
    Enable-WakeTimers
}

function Register-Schedule($python) {
    if ($Tool.Multi) { Register-Multi $python; return }
    $config = Read-Config
    Test-Config $config | Out-Null

    # pythonw = chay an, khong hien cua so.
    $pythonw = Join-Path (Split-Path $python) "pythonw.exe"
    if (-not (Test-Path $pythonw)) { $pythonw = $python }
    $action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$($Tool.Script)`" --once" -WorkingDirectory $ToolDir

    if ($Tool.Kind -eq "monitor") {
        $every = Get-Minutes $config "RUN_EVERY_MINUTES" 40
        $max = Get-Minutes $config "MAX_RUN_MINUTES" 20
        Step "Tao lich '$($Tool.TaskName)': quet moi $every phut, toi da $max phut/lan"
        $triggers = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $every)
        # Du phong: tool tu dung sau MAX_RUN_MINUTES; qua them 10 phut thi Windows tat han.
        $limit = New-TimeSpan -Minutes ($max + 10)
    } else {
        $times = Get-ScheduleTimes $config
        Step "Tao lich '$($Tool.TaskName)' luc: $($times -join ', ')"
        $triggers = foreach ($t in $times) { New-ScheduledTaskTrigger -Daily -At $t }
        $limit = [TimeSpan]::Zero
    }

    # -WakeToRun: may dang ngu (Sleep) thi Windows tu danh thuc de chay tool.
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -WakeToRun `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit $limit
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

    # -Force ghi de task cu; neu loi thi task cu van con nguyen.
    try {
        $null = Register-ScheduledTask -TaskName $Tool.TaskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Force
    } catch {
        Fail "Khong tao duoc lich: $($_.Exception.Message) Hay chay bang file .bat va bam 'Yes' khi Windows hoi quyen."
    }
    Ok "Da tao lich. Moi lan chay ghi ket qua vao log.txt"
    Enable-WakeTimers
}

function Enable-WakeTimers {
    # WakeToRun chi co tac dung khi Windows cho phep "hen gio danh thuc" (wake timers).
    # 1 = Enable, cho ca khi cam sac (AC) va dung pin (DC).
    Step "Cho phep Windows tu danh thuc may de chay tool"
    powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1 | Out-Null
    powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1 | Out-Null
    powercfg /setactive SCHEME_CURRENT | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Ok "Da bat. May ngu (Sleep) den gio chay se tu thuc day."
    } else {
        Write-Host "   Khong bat duoc (may co the da khoa chuc nang nay). Nen chinh Sleep = Never." -ForegroundColor Yellow
    }
}

function Remove-Schedule {
    if ($Tool.Multi) {
        Step "Xoa toan bo lich cua tool nay"
        $tasks = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
            $_.TaskName -like "$($Tool.TaskPrefix)*" -or $_.TaskName -eq $Tool.TaskName })
        foreach ($task in $tasks) { Unregister-ScheduledTask -TaskName $task.TaskName -Confirm:$false; Ok "Da xoa: $($task.TaskName)" }
        if (-not $tasks) { Ok "Khong co lich nao de xoa." }
        return
    }
    Step "Xoa lich '$($Tool.TaskName)'"
    if (Get-ScheduledTask -TaskName $Tool.TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Tool.TaskName -Confirm:$false
        Ok "Da xoa."
    } else {
        Ok "Khong co lich nao de xoa."
    }
}

# ------------------------------------------------------------------ main
switch ($Action) {
    "install" {
        $python = Install-Python
        Install-Playwright $python
        if ($Tool.Multi) {
            # Chi cai dat. Cau hinh + dang nhap Facebook lam trong giao dien (MO_TOOL.bat);
            # lich tu tao khi dang nhap thanh cong / bam Luu.
            Step "Cap nhat lich chay theo cau hinh hien co"
            $problem = Get-ConfigProblem (Read-Config)
            if ($problem) {
                Write-Host "   Chua cau hinh xong ($problem) -> chua tao lich." -ForegroundColor Yellow
            } else {
                Register-Multi $python
            }
            Write-Host ""
            Write-Host "   CAI DAT XONG. Mo MO_TOOL.bat de cau hinh va dang nhap Facebook." -ForegroundColor Green
            Write-Host "   Tai khoan nao chua dang nhap thi chua chay; dang nhap xong lich tu chay." -ForegroundColor Green
        } else {
            Ensure-Config $python
            Ensure-Login $python
            Register-Schedule $python
        }
    }
    "config" { Open-ConfigGui (Require-Python) }
    "gui" {
        # MO_TOOL.bat: mo giao dien bang pythonw (khong cua so den), khong doi.
        $python = Require-Python
        $pythonw = Join-Path (Split-Path $python) "pythonw.exe"
        if (-not (Test-Path $pythonw)) { $pythonw = $python }
        $env:PYTHONUTF8 = "1"
        Start-Process -FilePath $pythonw -ArgumentList "`"$(Script-Path 'cau_hinh')`"" -WorkingDirectory $ToolDir
        exit 0
    }
    "login" { Open-Login (Require-Python) }
    "schedule" { Register-Schedule (Require-Python) }
    "remove" { Remove-Schedule }
}

Write-Host "`n=== XONG ===" -ForegroundColor Green
