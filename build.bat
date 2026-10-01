@echo off
setlocal
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

echo [1/2] Установка зависимостей...
%PY% -m pip install -r requirements.txt pyinstaller || goto :error

echo [2/2] Сборка .exe...
%PY% -m PyInstaller cinema.spec --noconfirm || goto :error

echo.
echo Готово! Файл: dist\Kinofisha.exe
pause
exit /b 0

:error
echo.
echo Сборка не удалась.
pause
exit /b 1
