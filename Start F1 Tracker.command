#!/bin/bash
# Double-click to start the F1 Tracker (API + built web UI) and open it in your browser.
cd "$(dirname "$0")"
PORT=8000
if ! [ -x .venv/bin/uvicorn ]; then
  echo "Missing .venv - see README.md (Setup)."; read -r -p "Press Enter to close"; exit 1
fi
if ! [ -f .env ]; then
  echo "NOTE: no .env found. The site works, but AI narratives need ANTHROPIC_API_KEY in .env (copy .env.example)."
fi
if [ ! -d frontend/dist ]; then
  echo "Building the web UI (first run only)..."
  PATH="$PWD/.venv/bin:$PATH" .venv/bin/npm --prefix frontend install --no-fund --no-audit && PATH="$PWD/.venv/bin:$PATH" .venv/bin/npm --prefix frontend run build || { read -r -p "Build failed. Press Enter to close"; exit 1; }
fi
if lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Already running on http://127.0.0.1:$PORT"
else
  echo "Starting API + UI on http://127.0.0.1:$PORT  (close this window to stop)"
  ( sleep 1.5; open "http://127.0.0.1:$PORT" ) &
  PORT=$PORT exec .venv/bin/python scripts/serve.py
fi
open "http://127.0.0.1:$PORT"
