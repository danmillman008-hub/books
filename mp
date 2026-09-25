#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")" && pwd)"
[ -x "$ROOT/DeepTutor/.venv/bin/python" ] || "$ROOT/setup.sh"
cd "$ROOT/DeepTutor" && exec .venv/bin/python "$ROOT/mastery_cli.py" "$@"
