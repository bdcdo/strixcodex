#!/usr/bin/env bash
# Launch Strix AI pointed at the local strixcodex proxy.
# Starts the proxy in background if not already running.
#
# Strix runs inside a Docker container that maps host.docker.internal to the
# host. The proxy must therefore listen on 0.0.0.0 so the container can reach
# it, and Strix is told to dial host.docker.internal.
set -euo pipefail

PROXY_BIND="${STRIXCODEX_HOST:-0.0.0.0}"
PROXY_PORT="${STRIXCODEX_PORT:-8787}"
HEALTH_URL="http://127.0.0.1:${PROXY_PORT}/healthz"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Strix probes the LLM from the HOST first (interface/main.py:230) and only then
# spawns the container. So the LLM_API_BASE must resolve on both host and
# container. host.docker.internal works inside the container but does not
# resolve on the host on Linux. The docker0 bridge gateway (172.17.0.1) works
# from both sides.
DOCKER_BRIDGE_HOST="${STRIXCODEX_BRIDGE_IP:-$(ip -4 addr show docker0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)}"
DOCKER_BRIDGE_HOST="${DOCKER_BRIDGE_HOST:-172.17.0.1}"

if ! curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
  echo "[run-strix] starting strixcodex proxy on ${PROXY_BIND}:${PROXY_PORT}..." >&2
  (cd "$PROJECT_DIR" && uv run python -m strixcodex --host "$PROXY_BIND" --port "$PROXY_PORT") &
  PROXY_PID=$!
  trap 'kill $PROXY_PID 2>/dev/null || true' EXIT

  for _ in $(seq 1 30); do
    if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
  curl -fsS "$HEALTH_URL" >/dev/null || { echo "[run-strix] proxy failed to start" >&2; exit 1; }
fi

export STRIX_LLM="${STRIX_LLM:-openai/gpt-5.5}"
export LLM_API_KEY="${LLM_API_KEY:-codex-via-strixcodex}"
export LLM_API_BASE="http://${DOCKER_BRIDGE_HOST}:${PROXY_PORT}/v1"

echo "[run-strix] STRIX_LLM=${STRIX_LLM} LLM_API_BASE=${LLM_API_BASE}" >&2
exec strix "$@"
