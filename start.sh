#!/usr/bin/env bash
# Start the full stack: LLM bridge (agent plays the model) + DeepTutor API with LightRAG KB.
# Usage: ./start.sh          (after ./setup.sh on a fresh sandbox)
set -e
cd "$(dirname "$0")"
export DEEPTUTOR_HOME="$PWD/study/home" TIKTOKEN_CACHE_DIR="$PWD/study/tiktoken_cache" \
       HF_HUB_OFFLINE=1 SUMMARY_LANGUAGE=Persian
mkdir -p study/llm_bridge/{pending,answers} study/logs
pgrep -f "llm_bridge/server.py" >/dev/null || setsid nohup DeepTutor/.venv/bin/python llm_bridge/server.py > study/logs/bridge.log 2>&1 < /dev/null &
sleep 2
pgrep -f "deeptutor serve" >/dev/null || (cd DeepTutor && setsid nohup .venv/bin/deeptutor serve --host 127.0.0.1 --port 8001 > ../study/logs/api.log 2>&1 < /dev/null &)
echo "bridge :8765  api :8001  (logs in study/logs/)"
