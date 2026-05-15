@echo off
echo ============================================
echo Starting X Scraper Backend...
echo ============================================
cd /d "%~dp0backend"

echo Installing requirements...
pip install -r requirements.txt

echo.
echo Starting server on http://127.0.0.1:8000
echo ============================================
python main.py
pause
