#!/bin/bash
# Start script for WebUI service (Next.js frontend + FastAPI backend)

set -e

# Get port from environment (Cloud Run provides this)
FRONTEND_PORT="${PORT:-8080}"
BACKEND_PORT=$((FRONTEND_PORT + 1))

echo "========================================"
echo " Starting OSWorld WebUI Service"
echo "========================================"
echo "Frontend (Next.js): http://0.0.0.0:${FRONTEND_PORT}"
echo "Backend (FastAPI):  http://0.0.0.0:${BACKEND_PORT}"
echo "========================================"

# Start FastAPI backend in background
echo "Starting FastAPI backend on port ${BACKEND_PORT}..."
cd /app
python3 -m uvicorn orchestrator.webui_server:app \
  --host 0.0.0.0 \
  --port ${BACKEND_PORT} \
  --log-level info &

BACKEND_PID=$!
echo "FastAPI backend started with PID ${BACKEND_PID}"

# Wait for backend to be ready
echo "Waiting for backend to be ready..."
for i in {1..30}; do
  if curl -f http://localhost:${BACKEND_PORT}/api/health &>/dev/null; then
    echo "Backend is ready!"
    break
  fi
  echo "Waiting for backend... (${i}/30)"
  sleep 1
done

# Start Next.js frontend in foreground
echo "Starting Next.js frontend on port ${FRONTEND_PORT}..."
cd /app/webui-next

# Set API URL to point to localhost backend
export NEXT_PUBLIC_API_URL="http://localhost:${BACKEND_PORT}"

# Run Next.js in production mode
exec npm start -- -p ${FRONTEND_PORT} -H 0.0.0.0
