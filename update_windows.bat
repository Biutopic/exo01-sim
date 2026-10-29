@echo off
rem EXO-01 simulation - double-click to fetch the latest version from GitHub (Windows).
rem Needs Git for Windows (https://git-scm.com/download/win) or GitHub Desktop; the Python environment is kept.
cd /d "%~dp0"
where git >nul 2>&1
if errorlevel 1 (
  echo git is not installed. Install Git for Windows ^(https://git-scm.com/download/win^) or GitHub Desktop,
  echo or download the latest zip from the repository page instead.
  pause
  exit /b 1
)
if not exist ".git" (
  echo This folder is not a git checkout. Clone the repository once:
  echo    git clone https://github.com/Biutopic/exo01-sim.git
  echo then double-click update_windows.bat inside the cloned folder.
  pause
  exit /b 1
)
echo Fetching the latest version...
git pull --ff-only
if errorlevel 1 (
  echo Update failed - usually local edits in tracked files. Run:  git stash  then this file again.
  pause
  exit /b 1
)
echo Up to date. Start the app with start_windows.bat.
pause
