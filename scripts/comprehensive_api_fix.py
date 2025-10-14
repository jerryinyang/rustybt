#!/usr/bin/env python3
"""
Comprehensive fix for all API reference issues in documentation.
This script addresses all 157 fabricated/incorrect API references found in Story 10.X1.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set


# Load the verification report to understand all issues
def load_issues():
    with open("scripts/api_verification_report.json", "r") as f:
        return json.load(f)


def fix_file(file_path: Path, fixes: Dict[str, str], removals: Set[str]) -> int:
    """Apply fixes and removals to a single file."""
    changes = 0

    try:
        with open(file_path, "r") as f:
            content = f.read()

        original_content = content

        # Apply import fixes
        for old_import, new_import in fixes.items():
            if old_import in content:
                content = content.replace(old_import, new_import)
                changes += 1

        # Remove references to non-existent APIs
        for api_to_remove in removals:
            # Remove import lines
            content = re.sub(
                rf"^from rustybt.*import.*{api_to_remove}.*$", "", content, flags=re.MULTILINE
            )
            content = re.sub(
                rf"^import rustybt.*{api_to_remove}.*$", "", content, flags=re.MULTILINE
            )

            # Remove code examples that use the API
            # This is more complex - find code blocks that reference the API
            pattern = r"```python\n(.*?" + re.escape(api_to_remove) + r".*?)\n```"
            content = re.sub(
                pattern,
                "```python\n# Code example removed - API does not exist\n```",
                content,
                flags=re.DOTALL,
            )

            # Remove section headers about the API
            content = re.sub(rf"^#+\s*{api_to_remove}.*$", "", content, flags=re.MULTILINE)

        # Clean up multiple blank lines
        content = re.sub(r"\n\n\n+", "\n\n", content)

        if content != original_content:
            with open(file_path, "w") as f:
                f.write(content)
            changes += 1

    except Exception as e:
        print(f"Error processing {file_path}: {e}")

    return changes


def main():
    print("=" * 80)
    print("Comprehensive API Reference Fix")
    print("=" * 80)
    print()

    # Define all necessary fixes based on verification
    IMPORT_FIXES = {
        # TradingAlgorithm is in algorithm module
        "from rustybt import TradingAlgorithm": "from rustybt.algorithm import TradingAlgorithm",
        # run_algorithm is in utils.run_algo
        "from rustybt import run_algorithm": "from rustybt.utils.run_algo import run_algorithm",
        # Commission models - use the correct ones that exist
        "from rustybt.finance import PerShareCommission": "from rustybt.finance.commission import PerShareCommission",
        "from rustybt.finance.commission import PerShareCommission": "from rustybt.finance.commission import PerShareCommission",
        # Slippage models
        "from rustybt.finance import FixedSlippage": "from rustybt.finance.slippage import FixedSlippage",
        # symbol is not importable - it's a method on TradingAlgorithm
        # We'll handle this specially
    }

    # APIs that don't exist and should be removed
    APIS_TO_REMOVE = {
        # Analytics
        "RollingAnalytics",
        # Data/bundles
        "BundleMetadata",
        "register_bundle",
        "clean_cache",
        # Caching (doesn't exist)
        "CachedDataSource",
        "TTLFreshnessPolicy",
        "MarketCloseFreshnessPolicy",
        "HybridFreshnessPolicy",
        "YFinanceDataSource",  # Should be adapter
        # Live trading (not implemented yet)
        "CircuitBreaker",
        "CircuitBreakerConfig",
        "StateManager",
        "LiveTradingEngine",
        "PositionReconciler",
        "TradingScheduler",
        # Commission models that don't exist
        "MakerTakerFee",
        "PerAssetCommission",
        "PerDollarTiered",
        "PerShareTiered",
        # Slippage models that don't exist
        "PerAssetSlippage",
        # Finance/costs
        "BorrowCost",
        "MarginInterest",
        # Controls
        "RiskControl",
        # Metrics
        "MetricCalculator",
        # Testing utilities (don't exist)
        "BacktestRunner",
        "MockDataFeed",
        "detect_mocks",
        "detect_hardcoded_values",
        "generate_ohlcv",
        "generate_correlated_assets",
        "generate_regime_data",
        "valid_ohlcv_bar",
        "ohlcv_dataframe",
        # Optimization sampling (doesn't exist)
        "latin_hypercube_sample",
        "sobol_sample",
        # Data readers that don't exist
        "ParquetDailyBarReader",
        "PolarsDataPortal",
        # Adapters with wrong names
        "AlpacaAdapter  # More intraday history",
        "AlphaVantageAdapter  # Better international coverage",
    }

    # Process all markdown files
    docs_path = Path("docs/api")
    total_changes = 0
    files_changed = []

    for md_file in docs_path.rglob("*.md"):
        changes = fix_file(md_file, IMPORT_FIXES, APIS_TO_REMOVE)
        if changes > 0:
            total_changes += changes
            files_changed.append(md_file.name)
            print(f"✅ Fixed {changes} issues in {md_file.name}")

    # Special fixes for symbol usage
    print("\nApplying special fixes for symbol usage...")
    for md_file in docs_path.rglob("*.md"):
        try:
            with open(md_file, "r") as f:
                content = f.read()

            original = content

            # Remove incorrect symbol imports
            content = re.sub(r"from rustybt\.api import symbol.*\n", "", content)
            content = re.sub(r"from rustybt import symbol.*\n", "", content)

            # Fix symbol usage in code examples to use self.symbol()
            # Look for patterns like: symbol('AAPL') and replace with self.symbol('AAPL')
            # But only in algorithm contexts
            if "TradingAlgorithm" in content:
                content = re.sub(r"(?<!self\.)symbol\(", "self.symbol(", content)

            # Also fix get_datetime usage
            content = re.sub(r"from rustybt\.api import get_datetime.*\n", "", content)
            if "TradingAlgorithm" in content:
                content = re.sub(r"(?<!self\.)get_datetime\(", "self.get_datetime(", content)

            if content != original:
                with open(md_file, "w") as f:
                    f.write(content)
                print(f"✅ Fixed symbol/get_datetime usage in {md_file.name}")
                total_changes += 1

        except Exception as e:
            print(f"Error fixing symbol in {md_file}: {e}")

    print()
    print("=" * 80)
    print(f"SUMMARY: Fixed {total_changes} issues across {len(files_changed)} files")
    print("=" * 80)

    if files_changed:
        print("\nFiles changed:")
        for f in sorted(set(files_changed)):
            print(f"  - {f}")

    return total_changes > 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
