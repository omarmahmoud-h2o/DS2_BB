#!/bin/bash

set -e

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

CONDA_ENV="base"

COUNT=${1:-1000}
MAX_RETRIES=2
TEMPERATURE=0.8

PY="conda run --no-capture-output -n ${CONDA_ENV} python"

echo "=============================================="
echo "MLX banking-compliance generation"
echo "=============================================="
echo "Environment: ${CONDA_ENV}"
echo "Count:       ${COUNT}"
echo "Temperature: ${TEMPERATURE}"
echo "=============================================="

$PY "${PROJ}/scripts/generate_conversations.py" \
    --count "${COUNT}" \
    --max_retries "${MAX_RETRIES}" \
    --temperature "${TEMPERATURE}"

$PY "${PROJ}/scripts/validate_conversations.py" \
    --input "${PROJ}/output/banking_compliance_conversations.jsonl"

echo ""
echo "Pipeline completed successfully."