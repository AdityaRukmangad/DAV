#!/bin/bash
# Stop script for Question Engine

echo " Stopping Question Engine services..."

# Kill backend
if [ -f .backend.pid ]; then
    BACKEND_PID=$(cat .backend.pid)
    if kill -0 $BACKEND_PID 2>/dev/null; then
        echo "   Stopping backend (PID: $BACKEND_PID)..."
        kill $BACKEND_PID
    fi
    rm .backend.pid
fi

# Kill frontend
if [ -f .frontend.pid ]; then
    FRONTEND_PID=$(cat .frontend.pid)
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        echo "   Stopping frontend (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID
    fi
    rm .frontend.pid
fi

# Fallback: kill by port
pkill -f "uvicorn.*api:app" 2>/dev/null || true
pkill -f "vite.*3000" 2>/dev/null || true

echo " Services stopped"
