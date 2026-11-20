@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================================
echo     ОАО «ДОЛОМИТ» — ЗАПУСК ИГРЫ «ПОЛЕ ЧУДЕС»
echo ========================================================

rem 1. Генерация secret.key при первом запуске
if not exist "secret.key" (
    echo Генерация защищенного ключа secret.key...
    powershell -NoProfile -Command "$bytes = New-Object byte[] 32; [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes); [Convert]::ToBase64String($bytes) | Out-File -FilePath 'secret.key' -Encoding utf8 -NoNewline"
)

rem 2. Активация виртуального окружения Python (при наличии)
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

rem 3. Применение миграций базы данных
echo Проверка и обновление базы данных SQLite...
python manage.py migrate --noinput
if errorlevel 1 (
    echo [ОШИБКА] Не удалось применить миграции базы данных!
    pause
    exit /b 1
)

rem 4. Запуск скрипта киоска Chrome в фоновом процессе
echo Запуск интерфейса мультиборда в режиме киоска...
start "" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\kiosk.ps1"

rem 5. Запуск боевого сервера на 0.0.0.0:8000 (доступен по локальной сети)
echo.
echo Сервер слушает на 0.0.0.0:8000. Нажмите Ctrl+C для остановки.
echo.
python manage.py runserver 0.0.0.0:8000 --insecure
pause
