#!/bin/bash
# Startup script for Question Engine (Backend + Frontend)

set -e

echo "=========================================="
echo "  Question Engine - Full Stack Startup"
echo "=========================================="
echo ""

# Check if Python backend dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "  Backend dependencies not found. Please run:"
    echo "   pip install -r requirements.txt"
    exit 1
fi

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo " Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Start backend in background
echo " Starting backend server (port 8000)..."
python server.py > backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo " Waiting for backend to start..."
sleep 3

# Check if backend is running
if ! curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo " Backend failed to start. Check backend.log for errors."
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi
echo " Backend ready at http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"

# Start frontend
echo ""
echo " Starting frontend dev server (port 3000)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..
echo "   Frontend PID: $FRONTEND_PID"

echo ""
echo "=========================================="
echo "  Both services started successfully!"
echo "=========================================="
echo ""
echo " Frontend:  http://localhost:3000"
echo " Backend:   http://localhost:8000"
echo " API Docs:  http://localhost:8000/docs"
echo ""
echo " Logs:"
echo "   Backend:  tail -f backend.log"
echo "   Frontend: (shown below)"
echo ""
echo " To stop both services:"
echo "   kill $BACKEND_PID $FRONTEND_PID"
echo ""
echo "=========================================="

# Store PIDs for easy cleanup
echo $BACKEND_PID > .backend.pid
echo $FRONTEND_PID > .frontend.pid

# Wait for frontend process (keeps script running)
wait $FRONTEND_PID
