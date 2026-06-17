@echo off
setlocal
cd /d "%~dp0"

python -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1

python -m PyInstaller --clean --noconfirm WorldCupFloat.spec
if errorlevel 1 exit /b 1

echo.
echo Built: %CD%\dist\WorldCupFloat.exe
