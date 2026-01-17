#!/usr/bin/env bash
# Development script for running the backend API.

set -euo pipefail

# Activate local virtual environment if present
if [[ -f "../.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ../.venv/bin/activate
fi

uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload