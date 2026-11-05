@echo off
rem Double-click to start the app. Installs what is missing the first time, then opens the backend and frontend in their own windows and the browser.
setlocal
cd /d "%~dp0"

if not exist ".env" (
  echo The .env file is missing. Put it in %CD% ^(next to the backend and frontend folders^), then run this again.
  pause
  exit /b 1
)
where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found. Install Python 3 from python.org, tick "Add python.exe to PATH", then run this again.
  pause
  exit /b 1
)
where node >nul 2>&1
if errorlevel 1 (
  echo Node.js was not found. Install Node.js LTS from nodejs.org, then run this again.
  pause
  exit /b 1
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo First run: setting up the backend, this takes a few minutes...
  pushd backend
  python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
  if errorlevel 1 (
    echo Backend install failed.
    popd
    pause
    exit /b 1
  )
  popd
)
if not exist "frontend\node_modules" (
  echo First run: setting up the frontend, this takes a few minutes...
  pushd frontend
  call npm install --silent
  if errorlevel 1 (
    echo Frontend install failed.
    popd
    pause
    exit /b 1
  )
  popd
)

start "BACKEND - keep open" /D "%~dp0backend" cmd /k "set PYTHONUTF8=1&& .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"
start "FRONTEND - keep open" /D "%~dp0frontend" cmd /k "npm run dev"

echo Starting... the browser opens in a few seconds. Keep the BACKEND and FRONTEND windows open while you use the app.
timeout /t 12 /nobreak >nul
start "" http://localhost:5174
endlocal
