#!/bin/bash
# scripts/setup_tools.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash "${REPO_ROOT}/scripts/setup_verible.sh"
bash "${REPO_ROOT}/scripts/setup_verilator.sh"

# Temporarily extends path for script's child processes only. Permanent path handled by .envrc
export PATH="${REPO_ROOT}/.tools/verilator/bin:${REPO_ROOT}/.tools/verible/bin:${PATH}"

pip install -e ".[dev]"
pre-commit install

echo ""
echo "All tools ready:"
"${REPO_ROOT}/.tools/verible/bin/verible-verilog-lint" --version 2>&1 | head -1
"${REPO_ROOT}/.tools/verilator/bin/verilator" --version 2>&1 | head -1
