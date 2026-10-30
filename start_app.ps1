# Starts the whole app: installs what is missing the first time, then opens the backend and frontend in their own windows and the browser.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Need($cmd, $hint) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Write-Host "$cmd was not found. $hint" -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 } }
Need "python" "Install Python 3 from python.org (tick 'Add python.exe to PATH'), then run this again."
Need "node" "Install Node.js (LTS) from nodejs.org, then run this again."

if (-not (Test-Path "$root\.env")) { Write-Host "The .env file is missing. Put it in $root (next to the backend and frontend folders), then run this again." -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }
$cons = Select-String -Path "$root\.env" -Pattern "^\s*BOARD_CONSISTENCY_RUNS\s*=\s*([2-9])" -ErrorAction SilentlyContinue
if ($cons) { Write-Host "WARNING: .env sets BOARD_CONSISTENCY_RUNS above 1, so each assessment will run twice (Run A and Run B). Change it to 1 and run this again unless that is what you want." -ForegroundColor Yellow; Read-Host "Press Enter to continue anyway, or close this window to stop" }

$py = "$root\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "First run: setting up the backend (a few minutes)..." -ForegroundColor Cyan
  Set-Location "$root\backend"; python -m venv .venv
  & $py -m pip install -q -r requirements.txt; if ($LASTEXITCODE -ne 0) { Write-Host "Backend install failed." -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }
  Set-Location $root
}
if (-not (Test-Path "$root\frontend\node_modules")) {
  Write-Host "First run: setting up the frontend (a few minutes)..." -ForegroundColor Cyan
  Set-Location "$root\frontend"; npm install --silent; if ($LASTEXITCODE -ne 0) { Write-Host "Frontend install failed." -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }
  Set-Location $root
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='BACKEND - keep open'; Set-Location '$root\backend'; `$env:PYTHONUTF8='1'; & '$py' -m uvicorn app.main:app --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='FRONTEND - keep open'; Set-Location '$root\frontend'; npm run dev"
Write-Host "Starting... the browser opens in a few seconds. Keep the BACKEND and FRONTEND windows open while you use the app." -ForegroundColor Green
Start-Sleep 12
Start-Process "http://localhost:5174"
