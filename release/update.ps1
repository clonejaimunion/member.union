# =====================================================
#  تحديث سريع للنظام المحاسبي من GitHub
#  يُشغَّل بأمر واحد قصير:
#    [Net.ServicePointManager]::SecurityProtocol='Tls12'; iex (irm 'https://raw.githubusercontent.com/clonejaimunion/member.union/tradeunion-app/release/update.ps1')
#  ينزّل حزمة صغيرة (~3MB) ويطبّقها مع نسخة احتياطية تلقائية.
# =====================================================
$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$zipUrl = 'https://raw.githubusercontent.com/clonejaimunion/member.union/tradeunion-app/frontend/public/downloads/BankDepositSystemUpdate.zip'

Write-Host 'جارٍ تحميل حزمة التحديث من GitHub...' -ForegroundColor Cyan
$tmp = Join-Path $env:TEMP ('mu_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$zip = Join-Path $tmp 'update.zip'
Invoke-WebRequest -UseBasicParsing -Uri $zipUrl -OutFile $zip
Expand-Archive -Path $zip -DestinationPath $tmp -Force

# locate the update files (folder containing backend\server.py)
$p = $tmp
if (-not (Test-Path "$p\backend\server.py")) {
    $d = Get-ChildItem -Path $tmp -Recurse -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'backend\server.py') } | Select-Object -First 1
    if ($d) { $p = $d.FullName }
}
if (-not (Test-Path "$p\backend\server.py")) { Write-Host 'ملفات التحديث غير صحيحة' -ForegroundColor Red; return }

# detect installation directory
$t = @(
    "$env:LOCALAPPDATA\Bank Deposit Interest System",
    "$env:APPDATA\Bank Deposit Interest System",
    "$env:ProgramFiles\Bank Deposit Interest System",
    "${env:ProgramFiles(x86)}\Bank Deposit Interest System",
    "$env:ProgramFiles\BankDepositSystem",
    "${env:ProgramFiles(x86)}\BankDepositSystem",
    "C:\Bank Deposit Interest System"
) | Where-Object { Test-Path "$_\backend\server.py" } | Select-Object -First 1
if (-not $t) { Write-Host 'لم يتم العثور على مجلد تثبيت البرنامج' -ForegroundColor Red; return }
Write-Host "مجلد البرنامج: $t" -ForegroundColor Cyan

# stop running services
'python','pythonw','mongod','wscript' | ForEach-Object { Get-Process -Name $_ -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

# backup
$b = "$t\backup_$(Get-Date -Format yyyyMMdd_HHmmss)"
New-Item -ItemType Directory -Force -Path "$b\backend" | Out-Null
Copy-Item "$t\backend\server.py" "$b\backend\server.py" -Force
if (Test-Path "$t\frontend\build") { Copy-Item "$t\frontend\build" "$b\frontend_build" -Recurse -Force }

# apply backend
Copy-Item "$p\backend\server.py" "$t\backend\server.py" -Force
'deposit_notifications.py','requirements-runtime.txt' | ForEach-Object { if (Test-Path "$p\backend\$_") { Copy-Item "$p\backend\$_" "$t\backend\$_" -Force } }

# apply frontend
if (Test-Path "$t\frontend\build") { Remove-Item "$t\frontend\build" -Recurse -Force }
New-Item -ItemType Directory -Force -Path "$t\frontend\build" | Out-Null
Copy-Item "$p\frontend\*" "$t\frontend\build\" -Recurse -Force

# cleanup + relaunch
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "تم التحديث بنجاح. نسخة احتياطية: $b" -ForegroundColor Green
if (Test-Path "$t\launch_bank_deposit_system.vbs") { Start-Process "$t\launch_bank_deposit_system.vbs" }
