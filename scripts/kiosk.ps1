# kiosk.ps1 — Скрипт запуска табло «Поле чудес» в режиме киоска (Задача 18)

param (
    [string]$Port = "8000",
    [string]$DisplayPath = "display/"
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "     ОАО «ДОЛОМИТ» — ПОЛЕ ЧУДЕС: РЕЖИМ КИОСКА           " -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Определение локального IP-адреса для второго устройства (пульт ведущего)
$localIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.InterfaceAlias -notmatch 'Loopback' -and
    $_.IPAddress -notmatch '^169\.' -and
    $_.IPAddress -notmatch '^127\.'
} | Select-Object -First 1).IPAddress

if (-not $localIp) {
    $localIp = "127.0.0.1"
}

Write-Host ""
Write-Host " [Табло мультиборда]: http://localhost:$Port/$DisplayPath" -ForegroundColor Green
Write-Host " [Пульт ведущего]:   http://$($localIp):$Port/host/" -ForegroundColor Yellow
Write-Host " [Студия управления]: http://$($localIp):$Port/studio/" -ForegroundColor Yellow
Write-Host " [PIN-код доступа]:  1931" -ForegroundColor Magenta
Write-Host ""
Write-Host "Ожидание готовности сервера Django на порту $Port..." -ForegroundColor Gray

# 2. Ожидание запуска локального сервера
$serverReady = $false
$retries = 20
for ($i = 1; $i -le $retries; $i++) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", [int]$Port)
        $tcp.Close()
        $serverReady = $true
        break
    } catch {
        Start-Sleep -Milliseconds 600
    }
}

if (-not $serverReady) {
    Write-Host "Внимание: Сервер не ответил вовремя. Попытка открыть браузер..." -ForegroundColor Red
} else {
    Write-Host "Сервер готов! Запуск интерфейса табло..." -ForegroundColor Green
}

# 3. Поиск исполняемого файла Chrome или Edge
$browserPaths = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
)

$browserExe = $null
foreach ($path in $browserPaths) {
    if (Test-Path $path) {
        $browserExe = $path
        break
    }
}

$displayUrl = "http://127.0.0.1:$Port/$DisplayPath"

$kioskArgs = @(
    "--kiosk",
    "--app=$displayUrl",
    "--touch-events=enabled",
    "--disable-pinch",
    "--overscroll-history-navigation=0",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-features=Translate",
    "--check-for-update-interval=31536000",
    "$displayUrl"
)

if ($browserExe) {
    Write-Host "Запуск: $browserExe --kiosk $displayUrl" -ForegroundColor Cyan
    Start-Process -FilePath $browserExe -ArgumentList $kioskArgs
} else {
    Write-Host "Chrome/Edge не найдены по стандартным путям. Открытие через системный браузер..." -ForegroundColor Yellow
    Start-Process $displayUrl
}
