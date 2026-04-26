#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "============================================"
echo " Bank Deposit Interest System - Local Setup"
echo "============================================"

if [ ! -d "backend/.venv" ]; then
  python3 -m venv backend/.venv
fi

source backend/.venv/bin/activate
pip install -r backend/requirements.txt

cd frontend
yarn install
cd "$ROOT_DIR"

echo "Starting backend on http://localhost:8001"
(cd backend && source .venv/bin/activate && uvicorn server:app --host 0.0.0.0 --port 8001) &
BACKEND_PID=$!

echo "Starting frontend on http://localhost:3000"
(cd frontend && REACT_APP_BACKEND_URL=http://localhost:8001 yarn start) &
FRONTEND_PID=$!

echo "Admin URL: http://localhost:3000/secure-admin-control-panel"
echo "Press Ctrl+C to stop."
trap 'kill $BACKEND_PID $FRONTEND_PID' EXIT
wait
