@echo off
setlocal
cd /d "%~dp0"
echo.
echo  HealthBridge AI - starting up
echo  ==============================

where python >nul 2>nul || (echo Python was not found. Install Python 3.10+ from python.org & pause & exit /b 1)
where npm >nul 2>nul || (echo Node.js was not found. Install Node.js 18+ from nodejs.org & pause & exit /b 1)

if not exist "backend\venv\Scripts\python.exe" (
  echo [1/4] Creating Python virtual environment...
  python -m venv backend\venv || (pause & exit /b 1)
)
echo [2/4] Checking backend packages...
backend\venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt || (pause & exit /b 1)
if not exist "backend\.env" copy "backend\.env.example" "backend\.env" >nul

pushd frontend
if not exist "node_modules" (
  echo [3/4] Installing frontend packages...
  call npm install || (popd & pause & exit /b 1)
)
echo [3/4] Building the frontend...
call npm run build || (popd & pause & exit /b 1)
popd

echo [4/4] Starting server at http://127.0.0.1:8000  (press Ctrl+C to stop)
start "" http://127.0.0.1:8000
cd backend
venv\Scripts\python.exe run.py
