#!/usr/bin/env bash
# One-time (re)install of DeepTutor CLI + exam module in this workspace.
# The virtualenv is not persisted between sandbox sessions, so rerun this after a restart.
set -euo pipefail
cd "$(dirname "$0")/DeepTutor"
if [ ! -x .venv/bin/deeptutor ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -e ./packaging/deeptutor-cli
fi
echo "OK — use ./dt <command>   (e.g. ./dt exam packs)"
# server + LightRAG + local embeddings (knowledge base pipeline without API key)
.venv/bin/pip install -q "lightrag-hku==1.5.7" fastembed "fastapi>=0.100.0" "uvicorn[standard]>=0.24.0" "websockets>=12.0" \
  "python-multipart>=0.0.6" "bcrypt>=4.0.0" "python-jose[cryptography]>=3.3.0" "pocketbase>=0.12.0" "redis>=5.0.0,<7.0.0" \
  "loguru>=0.7.3,<1.0.0" "json-repair>=0.57.0,<1.0.0" "croniter>=6.0.0,<7.0.0" "psutil>=5.9.0,<8.0.0"
