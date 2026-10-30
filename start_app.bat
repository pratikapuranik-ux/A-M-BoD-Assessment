@echo off
rem Double-click to start the app (installs what is missing the first time).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_app.ps1"
