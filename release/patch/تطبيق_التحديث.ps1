# =====================================================
#  تحديث النظام المحاسبي عبر PowerShell (نسخ ملفات فقط)
#  فبراير 2026 - يعمل على جهاز العميل (Windows)
#  لا يعدّل السورس كود - ينسخ ملفات جاهزة فقط مع نسخة احتياطية
#  طريقة التشغيل:
#    كليك يمين على الملف -> Run with PowerShell
#    أو من نافذة PowerShell:
#      powershell -NoProfile -ExecutionPolicy Bypass -File ".\تطبيق_التحديث.ps1"
# =====================================================

$ErrorActionPreference = 'Stop'
try { chcp 65001 > $null } catch {}

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "   تحديث برنامج النظام المحاسبي (نسخة فبراير 2026)"    -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

# 1) مجلد ملفات التحديث (اللي فيه backend/ و frontend/) = نفس مكان السكربت
$PatchDir = $PSScriptRoot
if (-not $PatchDir) { $PatchDir = (Get-Location).Path }

if (-not (Test-Path (Join-Path $PatchDir 'backend\server.py'))) {
    Write-Host "[خطأ] لم يتم العثور على ملفات التحديث (backend\server.py) بجوار هذا السكربت." -ForegroundColor Red
    Read-Host "اضغط Enter للخروج"; exit 1
}

# 2) اكتشاف مجلد تثبيت البرنامج تلقائياً
$Candidates = @(
    "$env:LOCALAPPDATA\Bank Deposit Interest System",
    "$env:APPDATA\Bank Deposit Interest System",
    "$env:ProgramFiles\Bank Deposit Interest System",
    "${env:ProgramFiles(x86)}\Bank Deposit Interest System",
    "$env:ProgramFiles\BankDepositSystem",
    "${env:ProgramFiles(x86)}\BankDepositSystem",
    "C:\Bank Deposit Interest System"
)
$Target = $Candidates | Where-Object { Test-Path (Join-Path $_ 'backend\server.py') } | Select-Object -First 1

if (-not $Target) {
    Write-Host "[خطأ] لم يتم العثور على مجلد تثبيت البرنامج." -ForegroundColor Red
    Write-Host "ضع هذا الملف داخل مجلد تثبيت البرنامج ثم شغّله مرة أخرى."
    Read-Host "اضغط Enter للخروج"; exit 1
}
Write-Host "تم العثور على البرنامج في:" -ForegroundColor Green
Write-Host "  $Target"
Write-Host ""

# 3) إيقاف الخدمات الجارية
Write-Host "- إيقاف الخدمات الجارية ..." -ForegroundColor Yellow
foreach ($p in 'python','pythonw','mongod','wscript') {
    Get-Process -Name $p -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

# 4) نسخة احتياطية بالتاريخ والوقت (للرجوع لو لزم)
$Stamp  = Get-Date -Format 'yyyyMMdd_HHmmss'
$Backup = Join-Path $Target "backup_$Stamp"
Write-Host "- إنشاء نسخة احتياطية في: $Backup" -ForegroundColor Yellow
New-Item -ItemType Directory -Path (Join-Path $Backup 'backend') -Force | Out-Null
Copy-Item (Join-Path $Target 'backend\server.py') (Join-Path $Backup 'backend\server.py') -Force
if (Test-Path (Join-Path $Target 'frontend\build')) {
    Copy-Item (Join-Path $Target 'frontend\build') (Join-Path $Backup 'frontend_build') -Recurse -Force
}

# 5) تطبيق ملفات التحديث الجديدة (Backend + Frontend build)
Write-Host "- تحديث ملفات الـ Backend ..." -ForegroundColor Yellow
Copy-Item (Join-Path $PatchDir 'backend\server.py') (Join-Path $Target 'backend\server.py') -Force

# ملفات backend إضافية إن وُجدت في التحديث
foreach ($extra in 'deposit_notifications.py','requirements-runtime.txt') {
    $src = Join-Path $PatchDir ("backend\" + $extra)
    if (Test-Path $src) { Copy-Item $src (Join-Path $Target ("backend\" + $extra)) -Force }
}

Write-Host "- تحديث ملفات الواجهة (Frontend) ..." -ForegroundColor Yellow
$FeTarget = Join-Path $Target 'frontend\build'
if (Test-Path $FeTarget) { Remove-Item $FeTarget -Recurse -Force }
New-Item -ItemType Directory -Path $FeTarget -Force | Out-Null
Copy-Item (Join-Path $PatchDir 'frontend\*') $FeTarget -Recurse -Force

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host " تم تطبيق التحديث بنجاح"                                -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "نسخة احتياطية محفوظة في:"
Write-Host "  $Backup"
Write-Host ""
Write-Host "شغّل البرنامج من اختصار سطح المكتب لتجربة التحديثات."
Write-Host ""
Read-Host "اضغط Enter للخروج"
