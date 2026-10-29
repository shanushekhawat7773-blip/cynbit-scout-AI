@echo off
REM Cynbit Scout AI - Automated Windows Setup Script
REM Tested on Windows 10/11 with Python 3.10+

echo =======================================================
echo      CYNBIT SCOUT AI - WINDOWS ENVIRONMENT SETUP
echo =======================================================

echo [1/5] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python 3.10+ from python.org and check "Add Python to PATH".
    pause
    exit /b 1
)
python --version

echo.
echo [2/5] Creating Python virtual environment (.venv)...
if not exist ".venv" (
    python -m venv .venv
    echo Created virtual environment in .venv
) else (
    echo Existing .venv found.
)

echo.
echo [3/5] Activating virtual environment and installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo [4/5] Running automated verification test suite...
pytest tests/ -v --tb=short
if %errorlevel% neq 0 (
    echo Warning: Some tests failed. Please review the output above.
) else (
    echo All tests passed successfully!
)

echo.
echo [5/5] Generating synthetic benchmark dataset and running evaluation...
python scripts\generate_synthetic_data.py
python evaluation\evaluate.py

echo.
echo =======================================================
echo          CYNBIT SCOUT IS READY TO LAUNCH!
echo =======================================================
echo.
echo To start the interactive dashboard, run:
echo   .venv\Scripts\activate
echo   streamlit run app.py
echo.
set /p launch="Do you want to launch the Streamlit dashboard now? (y/n): "
if /i "%launch%"=="y" (
    streamlit run app.py
)
