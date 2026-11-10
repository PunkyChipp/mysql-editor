@echo off
setlocal
set PYTHONUTF8=1
cd /d "%~dp0"
py -3 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0home_setup.py"
  goto finished
)
python -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if not errorlevel 1 (
  python "%~dp0home_setup.py"
  goto finished
)
echo Install Python 3.12 or newer, select Add Python to PATH, then open this file again.
start "" "https://www.python.org/downloads/windows/"
pause
exit /b 1
:finished
if errorlevel 1 pause
endlocal
