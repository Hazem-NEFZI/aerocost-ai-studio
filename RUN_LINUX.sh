#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
PY=python3
if [ ! -d .venv ]; then
  "$PY" -m venv .venv
fi
source .venv/bin/activate
python -m pip install -r requirements.txt
(sleep 2; if command -v xdg-open >/dev/null; then xdg-open http://127.0.0.1:8502 >/dev/null 2>&1 || true; fi) &
python backend.py --port 8502
