#!/bin/bash
# Script to generate API documentation using pdoc
#
# Usage: ./scripts/generate_docs.sh

set -e

echo "🔍 Checking dependencies..."

# Check for pdoc
if ! python3 -c "import pdoc" 2>/dev/null; then
    echo "Installing pdoc..."
    pip install pdoc
fi

# Check for interrogate
if ! python3 -c "import interrogate" 2>/dev/null; then
    echo "Installing interrogate..."
    pip install interrogate
fi

echo ""
echo "📊 Generating docstring coverage report..."
interrogate rustybt/ \
    --generate-badge docs/contributing/interrogate_badge.svg \
    --badge-format svg \
    --verbose 2 \
    --fail-under 80 || true  # Don't fail the script

echo ""
echo "📚 Generating pdoc API documentation..."
pdoc rustybt \
    --output-dir docs/api-pdoc \
    --docformat google \
    --show-source \
    --search

echo ""
echo "✅ Documentation generation complete!"
echo ""
echo "Generated files:"
echo "  - docs/api-pdoc/        (pdoc HTML API docs)"
echo "  - docs/contributing/interrogate_badge.svg  (docstring coverage badge)"
echo ""
echo "To view the docs:"
echo "  python3 -m http.server --directory docs/api-pdoc 8000"
echo "  Then open: http://localhost:8000"
