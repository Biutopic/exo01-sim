#!/usr/bin/env bash
# EXO-01 simulation - start on macOS / Linux. Creates a private Python environment on first run.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Creating the Python environment in .venv (first run only, needs Python 3.11-3.13)..."
  python3 -m venv .venv || { echo "install Python 3.11+ first"; exit 1; }
fi
.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt || { echo "dependency installation failed"; exit 1; }
( sleep 3; command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:8050 || command -v open >/dev/null && open http://127.0.0.1:8050 ) &
exec .venv/bin/python app.py "$@"
