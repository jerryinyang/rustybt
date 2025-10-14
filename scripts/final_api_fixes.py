#!/usr/bin/env python3
"""
Final fixes for the remaining 18 fabricated API references.
"""

import re
from pathlib import Path


def apply_final_fixes():
    """Apply final fixes for remaining issues."""

    # Map of incorrect imports to correct ones or removals
    FINAL_FIXES = {
        # MonteCarloTester → MonteCarloSimulator (missed instance)
        "from rustybt.optimization import MonteCarloTester": "from rustybt.optimization import MonteCarloSimulator",
        "MonteCarloTester": "MonteCarloSimulator",
        # FixedSlippage is in slippage module, not commission
        "from rustybt.finance.commission import FixedSlippage": "from rustybt.finance.slippage import FixedSlippage",
        # Pipeline imports need to be corrected
        "from rustybt.pipeline import Column": "from rustybt.pipeline import Column",
        "from rustybt.pipeline import DataSet": "from rustybt.pipeline.data import DataSet",
        "from rustybt.pipeline.loaders import PipelineLoader": "from rustybt.pipeline.loaders import USEquityPricingLoader",
        # Parameter is likely in parameter_space module
        "from rustybt.optimization.parameter_space import Parameter": "from rustybt.optimization.parameter_space import ContinuousParameter",
        # Adapters - fix comments in imports
        "from rustybt.data.adapters import PolygonAdapter  # Real-time capable": "from rustybt.data.adapters import PolygonAdapter",
        # These don't exist and should be removed
        "from rustybt.data.bundles.adapter_bundles import ingest_from_datasource": "",
        "from rustybt.data.bundles.migration import migrate_to_parquet": "",
        "from rustybt.data.continuous_future_reader import ContinuousFutureReader": "",
        "from rustybt.data.dispatch_bar_reader import DispatchBarReader": "",
        "from rustybt.finance import PerformanceAnalyzer": "",
        "from rustybt.optimization import MultiObjectiveOptimizer": "",
        "from rustybt.optimization import DistributedOptimizer": "",
        "from rustybt.optimization import OptimizationDashboard": "",
        "from rustybt.optimization.search import IslandGeneticAlgorithm": "",
    }

    # Process all markdown files in docs/api
    docs_path = Path("docs/api")
    files_fixed = []

    for md_file in docs_path.rglob("*.md"):
        try:
            with open(md_file, "r") as f:
                content = f.read()

            original_content = content

            # Apply fixes
            for old_text, new_text in FINAL_FIXES.items():
                if old_text in content:
                    if new_text:
                        content = content.replace(old_text, new_text)
                    else:
                        # Remove the line entirely
                        content = re.sub(
                            rf"^.*{re.escape(old_text)}.*$\n?", "", content, flags=re.MULTILINE
                        )

            # Special handling for MonteCarloTester references in text
            content = content.replace("MonteCarloTester", "MonteCarloSimulator")
            content = content.replace("mc_tester", "mc_simulator")

            # Remove sections about non-existent features
            non_existent = [
                "MultiObjectiveOptimizer",
                "DistributedOptimizer",
                "OptimizationDashboard",
                "IslandGeneticAlgorithm",
                "PerformanceAnalyzer",
                "ContinuousFutureReader",
                "DispatchBarReader",
                "ingest_from_datasource",
                "migrate_to_parquet",
            ]

            for api in non_existent:
                # Remove section headers
                content = re.sub(rf"^#+\s*{api}.*$\n", "", content, flags=re.MULTILINE)

                # Remove code blocks containing the API
                pattern = rf"```python\n[^`]*{api}[^`]*\n```"
                content = re.sub(pattern, "", content, flags=re.DOTALL)

                # Remove paragraphs mentioning the API
                content = re.sub(rf"^.*{api}.*$\n", "", content, flags=re.MULTILINE)

            # Clean up multiple blank lines
            content = re.sub(r"\n\n\n+", "\n\n", content)
            content = re.sub(r"\n\n$", "\n", content)

            if content != original_content:
                with open(md_file, "w") as f:
                    f.write(content)
                files_fixed.append(md_file.name)
                print(f"✅ Fixed {md_file.name}")

        except Exception as e:
            print(f"❌ Error processing {md_file}: {e}")

    return files_fixed


def main():
    print("=" * 80)
    print("Final API Reference Fixes")
    print("=" * 80)
    print()

    files_fixed = apply_final_fixes()

    print()
    print("=" * 80)
    print(f"Fixed {len(files_fixed)} files")
    print("=" * 80)

    if files_fixed:
        print("\nFiles fixed:")
        for f in sorted(set(files_fixed)):
            print(f"  - {f}")


if __name__ == "__main__":
    main()
