#!/bin/bash
# scripts/setup_verible.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERIBLE_VERSION="v0.0-4080-ga0a8d8eb"
VERIBLE_DIR=".tools/verible"
ARCHIVE="verible-${VERIBLE_VERSION}-linux-static-x86_64.tar.gz"
VERIBLE_URL="https://github.com/chipsalliance/verible/releases/download/${VERIBLE_VERSION}/${ARCHIVE}"

mkdir -p "${VERIBLE_DIR}"

if [ -f "${VERIBLE_DIR}/bin/verible-verilog-lint" ]; then
    echo "Verible already installed at ${VERIBLE_DIR}"
    echo "Version: $("${VERIBLE_DIR}/bin/verible-verilog-lint" --version 2>&1 | head -1)"
    echo "To reinstall, remove ${VERIBLE_DIR} and run this script again."
    exit 0
fi

echo "Downloading Verible ${VERIBLE_VERSION}..."
if ! wget -q "${VERIBLE_URL}" -O "${VERIBLE_DIR}/${ARCHIVE}"; then
    echo "Error: Failed to download Verible ${VERIBLE_VERSION}"
    echo "URL attempted: ${VERIBLE_URL}"
    exit 1
fi

echo "Extracting..."
tar -xzf "${VERIBLE_DIR}/${ARCHIVE}" -C "${VERIBLE_DIR}" --strip-components=1
rm "${VERIBLE_DIR}/${ARCHIVE}"

echo ""
echo "Verible ${VERIBLE_VERSION} installed successfully!"
echo "Binary location: ${VERIBLE_DIR}/bin/verible-verilog-lint"
echo ""
echo "Version info:"
"${VERIBLE_DIR}/bin/verible-verilog-lint" --version 2>&1 | head -1
