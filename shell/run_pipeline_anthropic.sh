#!/bin/bash
# Generate + validate synthetic banking-compliance conversations using the Anthropic API.
#
# Usage: ./shell/run_pipeline_anthropic.sh <count> [--max_retries N] [--temperature T] [--start_index N]
#
# Requires ANTHROPIC_API_KEY to be set. Optionally set ANTHROPIC_MODEL (defaults to claude-sonnet-5).

COUNT=${1:-50}
PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
shift 2>/dev/null || true

export USE_ANTHROPIC=1

echo "Generating ${COUNT} FAG conversations (Anthropic: ${ANTHROPIC_MODEL:-claude-sonnet-5})"
python "${PROJ_DIR}/scripts/generate_conversations.py" --count "${COUNT}" "$@"

python "${PROJ_DIR}/scripts/validate_conversations.py" \
    --input "${PROJ_DIR}/output/vrm_fag_conversations.jsonl"

echo "[done]"
