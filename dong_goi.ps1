# (c) 2026 BanhBaoChien AutoTool. Bao luu moi quyen.
# Dong goi ban gui khach: chi file .pyc (an ma nguon .py doc duoc) + .bat + .ps1 + requirements.
#   powershell -ExecutionPolicy Bypass -File dong_goi.ps1 [-Out <thu muc>]
# Luu y: .pyc chi chay dung tren Python 3.12 (setup.ps1 cai dung 3.12). Can bao ve manh hon (chong
#        dich nguoc) -> mua PyArmor ban tra phi hoac dong goi .exe bang Nuitka (lam o buoc sau).
param([string]$Out = "")
$ErrorActionPreference = "Stop"
$ToolDir = $PSScriptRoot
if (-not $Out) { $Out = Join-Path (Split-Path $ToolDir) "FacebookTool_GuiKhach" }

function Find-Python {
    foreach ($cmd in "py", "python") {
        $f = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($f -and $f.Source -notmatch "WindowsApps") { return $f.Source }
    }
    Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}
$python = Find-Python
if (-not $python) { Write-Host "Khong thay Python." -ForegroundColor Red; exit 1 }

Write-Host ">> Chuan bi thu muc: $Out" -ForegroundColor Cyan
if (Test-Path $Out) { Remove-Item $Out -Recurse -Force }
New-Item -ItemType Directory -Path $Out | Out-Null

# 1. Bien dich .py -> .pyc (dat canh file, khong dung thu muc __pycache__).
Write-Host ">> Bien dich .pyc"
& $python -c "import compileall,sys; sys.exit(0 if compileall.compile_dir(r'$ToolDir', maxlevels=0, legacy=True, quiet=1, force=True) else 1)"
if ($LASTEXITCODE -ne 0) { Write-Host "Bien dich that bai." -ForegroundColor Red; exit 1 }

# 2. Chep .pyc + cac file khong phai ma nguon. KHONG chep .py, du lieu khach, khoa ban quyen.
$exclude = @("license.key", "config.json", "config.json.bak", "config.json.tmp")
$excludeDir = @("accounts", "campaigns", "logs", "anh_loi", "__pycache__", "_cu")
foreach ($f in Get-ChildItem $ToolDir -File) {
    if ($f.Extension -eq ".py") { continue }
    if ($f.Name -in $exclude) { continue }
    if ($f.Name -eq "dong_goi.ps1") { continue }
    Copy-Item $f.FullName (Join-Path $Out $f.Name)
}
# Xoa .pyc vua tao trong thu muc goc (giu thu muc goc sach).
Get-ChildItem $ToolDir -Filter *.pyc -File | Remove-Item -Force

Write-Host ">> Xong. Ban gui khach o: $Out" -ForegroundColor Green
Write-Host "   Kiem tra: trong $Out chi co .pyc, khong co file .py nao." -ForegroundColor Green
$leftPy = Get-ChildItem $Out -Filter *.py -File -ErrorAction SilentlyContinue
if ($leftPy) { Write-Host "   CANH BAO: van con file .py: $($leftPy.Name -join ', ')" -ForegroundColor Yellow }
