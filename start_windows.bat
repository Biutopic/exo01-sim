@echo off
rem EXO-01 simulation - double-click to start (Windows).
rem Uses an environment that already has the dependencies (%USERPROFILE%\.venv or .venv here); otherwise creates .venv and installs them.
cd /d "%~dp0"
set PY=
if exist "%USERPROFILE%\.venv\Scripts\python.exe" (
  "%USERPROFILE%\.venv\Scripts\python.exe" -c "import capytaine, flask" >nul 2>&1 && set PY=%USERPROFILE%\.venv\Scripts\python.exe
)
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
if "%PY%"=="" (
  echo Creating the Python environment in .venv (first run only, needs Python 3.11-3.13 installed)...
  py -3.13 -m venv .venv 2>nul || py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv 2>nul || python -m venv .venv
  if not exist ".venv\Scripts\python.exe" (
    echo Could not create the environment: install Python 3.11+ from python.org and run this file again.
    pause
    exit /b 1
  )
  set PY=.venv\Scripts\python.exe
)
echo Using %PY%
echo Checking dependencies (quick when already installed)...
"%PY%" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed - check the internet connection, then run this file again.
  pause
  exit /b 1
)
echo Starting the server; the browser opens at http://127.0.0.1:8050 (close this window or press Ctrl+C to stop).
start "" "http://127.0.0.1:8050"
"%PY%" app.py
pause
