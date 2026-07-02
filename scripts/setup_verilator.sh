#!/bin/bash
# scripts/setup_verilator.sh
# NOTE: Verilator does not ship prebuilt binaries — built from source.
# cocotb 2.0 requires Verilator >= 5.036. Pinning to 5.040.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERILATOR_VERSION="5.040"
VERILATOR_DIR="${REPO_ROOT}/.tools/verilator"
VERILATOR_BUILD_DIR="/tmp/verilator-build-${VERILATOR_VERSION}"
VERILATOR_URL="https://github.com/verilator/verilator/archive/refs/tags/v${VERILATOR_VERSION}.tar.gz"

mkdir -p "${VERILATOR_DIR}"

if [ -f "${VERILATOR_DIR}/bin/verilator" ]; then
    echo "Verilator already installed at ${VERILATOR_DIR}"
    echo "Version: $("${VERILATOR_DIR}/bin/verilator" --version 2>&1 | head -1)"
    echo "To reinstall, remove ${VERILATOR_DIR} and run this script again."
    exit 0
fi

trap 'echo "Error: build failed. Cleaning up..."; rm -rf "${VERILATOR_BUILD_DIR}" "${VERILATOR_DIR}"; exit 1' ERR

if [ -d "${VERILATOR_BUILD_DIR}" ]; then
    echo "Removing stale build directory ${VERILATOR_BUILD_DIR}..."
    rm -rf "${VERILATOR_BUILD_DIR}"
fi

echo "Installing Verilator build dependencies..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    autoconf \
    bison \
    flex \
    g++ \
    help2man \
    libfl-dev \
    make \
    zlib1g-dev

echo "Downloading Verilator v${VERILATOR_VERSION} source..."
if ! wget -q "${VERILATOR_URL}" -O "/tmp/verilator-${VERILATOR_VERSION}.tar.gz"; then
    echo "Error: Failed to download Verilator v${VERILATOR_VERSION}"
    echo "URL attempted: ${VERILATOR_URL}"
    exit 1
fi

echo "Extracting..."
mkdir -p "${VERILATOR_BUILD_DIR}"
tar -xzf "/tmp/verilator-${VERILATOR_VERSION}.tar.gz" \
    -C "${VERILATOR_BUILD_DIR}" --strip-components=1
rm "/tmp/verilator-${VERILATOR_VERSION}.tar.gz"

echo "Building Verilator v${VERILATOR_VERSION} (this takes a few minutes)..."
cd "${VERILATOR_BUILD_DIR}"
autoconf
unset VERILATOR_ROOT          # avoid conflicts with any system install
./configure --prefix="${VERILATOR_DIR}"
make -j"$(nproc)"
make install
cd "${REPO_ROOT}"

rm -rf "${VERILATOR_BUILD_DIR}"

echo ""
echo "Verilator v${VERILATOR_VERSION} installed successfully!"
echo "Binary location: ${VERILATOR_DIR}/bin/verilator"
echo ""
echo "Version info:"
"${VERILATOR_DIR}/bin/verilator" --version 2>&1 | head -1
