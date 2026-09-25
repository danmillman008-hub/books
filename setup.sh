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
