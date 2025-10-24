#!/bin/bash
#
# Privacy Scanner for Documentation
#
# This script scans documentation files for personal information that should
# not be published publicly. It checks for:
# - Personal file paths (e.g., /Users/username)
# - Development organization names
# - Private IP addresses
# - Email addresses
# - API keys and tokens
#
# Exit codes:
#   0 - No issues found
#   1 - Personal information found (blocking)
#   2 - Warnings found (non-blocking)

set -e

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Counters
ERRORS=0
WARNINGS=0

# Documentation directories to scan (public-facing only)
PUBLIC_DIRS=(
    "docs/examples"
    "docs/api"
    "docs/guides"
    "docs/getting-started"
    "docs/about"
    "docs/index.md"
)

echo "🔍 Running Privacy Scanner for Documentation"
echo "=============================================="
echo ""

# Check if we're in the right directory
if [ ! -d "docs" ]; then
    echo -e "${RED}ERROR: Must be run from repository root${NC}"
    exit 1
fi

# Function to check for pattern and report findings
check_pattern() {
    local pattern="$1"
    local description="$2"
    local severity="$3"  # "error" or "warning"
    local files_found=0

    for dir in "${PUBLIC_DIRS[@]}"; do
        if [ ! -e "$dir" ]; then
            continue
        fi

        # Search for pattern (|| true prevents set -e from exiting on no matches)
        if grep -r -l -E "$pattern" "$dir" 2>/dev/null | grep -v "node_modules" | grep -v ".git" || false; then
            files_found=1
        fi
    done

    if [ $files_found -eq 1 ]; then
        if [ "$severity" = "error" ]; then
            echo -e "${RED}✗ ERROR:${NC} $description"
            ERRORS=$((ERRORS + 1))
        else
            echo -e "${YELLOW}⚠ WARNING:${NC} $description"
            WARNINGS=$((WARNINGS + 1))
        fi
        echo ""
    fi

    return 0  # Always return 0 to prevent set -e from exiting
}

echo "Scanning for personal information patterns..."
echo ""

# Check for personal file paths
check_pattern "/Users/[a-zA-Z0-9_-]+" \
    "Personal file paths found (e.g., /Users/username)" \
    "error"

check_pattern "/home/[a-zA-Z0-9_-]+/[a-zA-Z]" \
    "Personal home directories found (e.g., /home/username)" \
    "error"

# Check for development organization names
check_pattern "bmad-dev" \
    "Development organization name 'bmad-dev' found (should use public org name)" \
    "warning"

# Check for private IP addresses (excluding common examples like 127.0.0.1)
# Pattern requires word boundary before IP to avoid matching prices like 110.0
check_pattern "([^0-9]|^)(192\.168\.[0-9]{1,3}\.[0-9]{1,3}|10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3})([^0-9]|$)" \
    "Private IP addresses found" \
    "warning"

# Check for email addresses
check_pattern "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}" \
    "Email addresses found" \
    "warning"

# Check for API keys and tokens (common patterns)
check_pattern "(api[_-]?key|apikey|api[_-]?secret).*[:=].*['\"][a-zA-Z0-9]{20,}['\"]" \
    "Potential API keys found" \
    "error"

check_pattern "sk-[a-zA-Z0-9]{20,}" \
    "Potential OpenAI API keys found (sk-...)" \
    "error"

check_pattern "AKIA[0-9A-Z]{16}" \
    "Potential AWS access keys found (AKIA...)" \
    "error"

check_pattern "ghp_[a-zA-Z0-9]{36}" \
    "Potential GitHub personal access tokens found (ghp_...)" \
    "error"

# Check for passwords in code examples
check_pattern "password['\"]?\s*[:=]\s*['\"][^'\"]{8,}['\"]" \
    "Potential hardcoded passwords found" \
    "error"

# Check for notebook outputs with file paths (special check for .ipynb files)
echo "Checking Jupyter notebooks for output cells with personal paths..."
for dir in "${PUBLIC_DIRS[@]}"; do
    if [ ! -e "$dir" ]; then
        continue
    fi

    # Find all notebooks - use simple for loop instead of process substitution
    if notebooks=$(find "$dir" -name "*.ipynb" 2>/dev/null); then
        for notebook in $notebooks; do
            if [ -f "$notebook" ]; then
                if grep -q '"output_type"' "$notebook" 2>/dev/null; then
                    if grep -q "/Users/[a-zA-Z0-9_-]\+" "$notebook" 2>/dev/null; then
                        echo -e "${RED}✗ ERROR:${NC} Notebook has output cells with personal paths: $notebook"
                        ERRORS=$((ERRORS + 1))
                    fi
                fi
            fi
        done
    fi
done

echo ""
echo "=============================================="
echo "Scan Complete"
echo "=============================================="
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ No issues found - documentation is clean${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Found $WARNINGS warning(s) - review recommended but not blocking${NC}"
    exit 0  # Changed from exit 2 to exit 0 - warnings don't block commits
else
    echo -e "${RED}✗ Found $ERRORS error(s) and $WARNINGS warning(s)${NC}"
    echo -e "${RED}✗ BLOCKING: Fix errors before committing/publishing${NC}"
    exit 1
fi
