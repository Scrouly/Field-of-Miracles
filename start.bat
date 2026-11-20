@echo off
chcp 65001 >nul
rem Запуск «Поля чудес»: сервер на этом компьютере. На этом этапе только сервер,
rem открытие Chrome в режиме киоска добавится в задаче 18.
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

python manage.py migrate --noinput
python manage.py runserver 127.0.0.1:8000
pause
