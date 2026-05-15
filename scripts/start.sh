#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.nvm/versions/node/v22.22.3/bin:$PATH"

cd "$ROOT"

echo "Starting FastAPI..."
uvicorn src.main:app --reload --port 8000 &
BACKEND_PID=$!

echo "Starting Vite..."
cd "$ROOT/frontend"
npx vite --port 5173 &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT INT TERM

echo ""
echo "  API:      http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  Docs:     http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop."
wait
