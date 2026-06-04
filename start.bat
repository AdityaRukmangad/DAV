@echo off
REM Startup script for Question Engine (Backend + Frontend) - Windows version

echo ==========================================
echo   Question Engine - Full Stack Startup
echo ==========================================
echo.

REM Start backend in background
echo [*] Starting backend server (port 8000)...
start /B python server.py > backend.log 2>&1

REM Wait for backend to be ready
echo [*] Waiting for backend to start...
timeout /t 5 /nobreak > nul

REM Check if backend is running (optional, may fail if curl not available)
echo [*] Backend should be running at http://localhost:8000
echo     API Docs: http://localhost:8000/docs
echo.

REM Start frontend
echo [*] Starting frontend dev server (port 3000)...
cd frontend
start /B npm run dev
cd ..

echo.
echo ==========================================
echo   Both servers started!
echo   Backend: http://localhost:8000
echo   Frontend: http://localhost:5173 (or check terminal)
echo   Press Ctrl+C to stop
echo ==========================================
echo.

REM Keep the window open
pause
