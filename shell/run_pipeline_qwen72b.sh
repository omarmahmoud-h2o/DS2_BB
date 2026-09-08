#!/bin/bash
# Generate + validate synthetic banking-compliance conversations using a local vLLM server (Qwen 4B).
#
# Usage: ./shell/run_pipeline_qwen4b.sh <count> [--server-only] [--no-server]

COUNT=${1:-50}
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

CONDA_ENV="coact311"
MODEL="Qwen/Qwen3.5-4B"
MODEL_ALIAS="Qwen3.5-4B"
PORT=8001
TP=4
GPUS="0"
MAX_LEN=5200
MEM_UTIL=0.95
DTYPE="bfloat16"

MAX_RETRIES=2
TEMPERATURE=0.8

SERVER_ONLY=false; NO_SERVER=false
shift 2>/dev/null || true
for arg in "$@"; do
    case $arg in
        --server-only) SERVER_ONLY=true ;;
        --no-server)   NO_SERVER=true   ;;
    esac
done

unset USE_ANTHROPIC 2>/dev/null || true
export VLLM_API_BASE="http://localhost:${PORT}/v1"
API_URL="${VLLM_API_BASE}/models"

# ── vLLM server ──────────────────────────────────────────────────
if [[ "$NO_SERVER" == false ]]; then
    if ! curl -sf "${API_URL}" >/dev/null 2>&1; then
        CUDA_VISIBLE_DEVICES=${GPUS} VLLM_WORKER_MULTIPROC_METHOD=spawn \
            conda run --no-capture-output -n "${CONDA_ENV}" \
            python -m vllm.entrypoints.openai.api_server \
                --model "${MODEL}" --served-model-name "${MODEL_ALIAS}" \
                --host 0.0.0.0 --port "${PORT}" \
                --tensor-parallel-size "${TP}" --max-model-len "${MAX_LEN}" \
                --gpu-memory-utilization "${MEM_UTIL}" --dtype "${DTYPE}" \
                --trust-remote-code --enable-prefix-caching &
        echo "$!" > "${PROJ}/.vllm.pid"
        elapsed=0
        while ! curl -sf "${API_URL}" >/dev/null 2>&1; do
            sleep 5; elapsed=$((elapsed+5))
            [[ $elapsed -ge 600 ]] && exit 1
        done
    fi
fi
[[ "$SERVER_ONLY" == true ]] && exit 0

PY="conda run -n ${CONDA_ENV} python"

$PY "${PROJ}/scripts/generate_conversations.py" --count "${COUNT}" \
    --max_retries "${MAX_RETRIES}" --temperature "${TEMPERATURE}"

$PY "${PROJ}/scripts/validate_conversations.py" \
    --input "${PROJ}/output_qwen/banking_compliance_conversations_qwen.jsonl"
