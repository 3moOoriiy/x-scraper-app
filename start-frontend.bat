@echo off
echo ============================================
echo Starting X Scraper Frontend...
echo ============================================
cd /d "%~dp0frontend"

if not exist node_modules (
    echo Installing dependencies...
    call npm install
)

echo.
echo Starting React app on http://localhost:3000
echo ============================================
call npm run dev
pause
