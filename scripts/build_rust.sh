#!/usr/bin/env bash
#
# Build Rust extensions for RustyBT
#
# Usage:
#   ./scripts/build_rust.sh [dev|release]
#
# Arguments:
#   dev     - Build in development mode (default, faster builds, no optimizations)
#   release - Build in release mode (optimized, slower builds)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Determine build mode
BUILD_MODE="${1:-dev}"

# Check if we're in the project root
if [ ! -d "rust" ]; then
    echo -e "${RED}Error: rust/ directory not found${NC}"
    echo "Please run this script from the project root directory"
    exit 1
fi

# Check if Rust is installed
if ! command -v cargo &> /dev/null; then
    echo -e "${RED}Error: Rust toolchain not found${NC}"
    echo "Install Rust from: https://rustup.rs/"
    exit 1
fi

# Check if maturin is installed
if ! command -v maturin &> /dev/null; then
    echo -e "${YELLOW}Warning: maturin not found, installing...${NC}"
    pip install maturin
fi

# Build based on mode
cd rust

case "$BUILD_MODE" in
    dev|develop|development)
        echo -e "${GREEN}Building Rust extension (development mode)...${NC}"
        maturin develop
        ;;

    release|prod|production)
        echo -e "${GREEN}Building Rust extension (release mode)...${NC}"
        maturin build --release
        echo -e "${GREEN}Wheel created in rust/target/wheels/${NC}"
        ;;

    *)
        echo -e "${RED}Error: Invalid build mode: $BUILD_MODE${NC}"
        echo "Usage: $0 [dev|release]"
        exit 1
        ;;
esac

echo -e "${GREEN}✓ Build complete!${NC}"
echo ""
echo "Test the extension:"
echo "  python -c \"from rustybt import rust_sum; print(rust_sum(2, 3))\""
echo ""
echo "Run tests:"
echo "  pytest tests/rust/ -v"
