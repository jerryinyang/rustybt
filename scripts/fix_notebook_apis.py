#!/usr/bin/env python3
"""
Fix critical API errors in advanced tutorial notebooks.

This script corrects fabricated/incorrect APIs found during documentation review.
"""

import json
import sys
from pathlib import Path

def fix_notebook(notebook_path: Path) -> tuple[int, list[str]]:
    """Fix API errors in a single notebook."""
    fixes_applied = 0
    fixes_list = []

    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)

    for cell in notebook.get('cells', []):
        if cell.get('cell_type') != 'code':
            continue

        source = ''.join(cell.get('source', []))
        original_source = source

        # Fix 1: MACD -> MACDSignal
        if 'from rustybt.pipeline.factors import' in source and 'MACD' in source:
            source = source.replace('MACD,', 'MACDSignal,')
            source = source.replace('macd = MACD()', 'macd = MACDSignal()')
            if source != original_source:
                fixes_applied += 1
                fixes_list.append("Replaced MACD with MACDSignal")

        # Fix 2: Remove AverageTrueRange (doesn't exist)
        if 'AverageTrueRange' in source:
            # Comment it out with explanation
            source = source.replace(
                'from rustybt.pipeline.factors import (\n',
                'from rustybt.pipeline.factors import (\n    # Note: AverageTrueRange not available, use TrueRange\n'
            )
            source = source.replace(
                'AverageTrueRange,',
                '# AverageTrueRange,  # Not available - use TrueRange + SMA'
            )
            source = source.replace(
                'atr = AverageTrueRange(window_length=14)',
                '# atr = AverageTrueRange(window_length=14)  # Not available\ntr = TrueRange()\natr = SimpleMovingAverage(inputs=[tr], window_length=14)'
            )
            if source != original_source:
                fixes_applied += 1
                fixes_list.append("Fixed AverageTrueRange usage")

        # Fix 3: GridSearch -> GridSearchAlgorithm
        if 'GridSearch' in source and 'GridSearchAlgorithm' not in source:
            source = source.replace('GridSearch()', 'GridSearchAlgorithm(parameter_space)')
            source = source.replace(
                'from rustybt.optimization import (\n',
                'from rustybt.optimization import (\n'
            )
            source = source.replace(
                'GridSearch,',
                '# GridSearch,  # Should be GridSearchAlgorithm from search module'
            )
            if 'from rustybt.optimization.search import' not in source:
                source = 'from rustybt.optimization.search import GridSearchAlgorithm\n' + source
            if source != original_source:
                fixes_applied += 1
                fixes_list.append("Replaced GridSearch with GridSearchAlgorithm")

        # Fix 4: BayesianOptimization -> BayesianOptimizer
        if 'BayesianOptimization' in source:
            source = source.replace('BayesianOptimization', 'BayesianOptimizer')
            if source != original_source:
                fixes_applied += 1
                fixes_list.append("Replaced BayesianOptimization with BayesianOptimizer")

        # Fix 5: KellyAllocation -> KellyCriterionAllocation
        if 'KellyAllocation' in source and 'KellyCriterionAllocation' not in source:
            source = source.replace('KellyAllocation', 'KellyCriterionAllocation')
            if source != original_source:
                fixes_applied += 1
                fixes_list.append("Replaced KellyAllocation with KellyCriterionAllocation")

        # Fix 6: SharpeRatio() -> ObjectiveFunction(metric="sharpe_ratio")
        if 'SharpeRatio()' in source:
            source = source.replace('SharpeRatio()', 'ObjectiveFunction(metric="sharpe_ratio")')
            source = source.replace('SortinoRatio()', 'ObjectiveFunction(metric="sortino_ratio")')
            source = source.replace('CalmarRatio()', 'ObjectiveFunction(metric="calmar_ratio")')
            # Remove bad imports
            source = source.replace('SharpeRatio, SortinoRatio, CalmarRatio', 'ObjectiveFunction, ObjectiveMetric')
            if source != original_source:
                fixes_applied += 1
                fixes_list.append("Fixed objective function usage")

        # Fix 7: TrailingStopLimitOrder (doesn't exist)
        if 'TrailingStopLimitOrder' in source:
            source = source.replace(
                'TrailingStopLimitOrder,',
                '# TrailingStopLimitOrder,  # Not available - only TrailingStopOrder exists'
            )
            source = source.replace(
                'from rustybt.finance.execution import (\n',
                'from rustybt.finance.execution import (\n    # Note: TrailingStopLimitOrder not available\n'
            )
            if source != original_source:
                fixes_applied += 1
                fixes_list.append("Commented out TrailingStopLimitOrder (not available)")

        # Fix 8: Order status strings -> enum
        if "order_obj.status == 'open'" in source:
            # Add import if not present
            if 'from rustybt.finance.order import ORDER_STATUS' not in source:
                source = 'from rustybt.finance.order import ORDER_STATUS\n' + source
            source = source.replace("order_obj.status == 'open'", "order_obj.status == ORDER_STATUS.OPEN")
            source = source.replace("order_obj.status == 'held'", "order_obj.status == ORDER_STATUS.HELD")
            source = source.replace("order_obj.status == 'partial'", "order_obj.status == ORDER_STATUS.PARTIALLY_FILLED")
            source = source.replace("order_obj.status == 'filled'", "order_obj.status == ORDER_STATUS.FILLED")
            source = source.replace("order_obj.status == 'canceled'", "order_obj.status == ORDER_STATUS.CANCELED")
            if source != original_source:
                fixes_applied += 1
                fixes_list.append("Fixed order status enum usage")

        # Update cell source if changed
        if source != original_source:
            cell['source'] = source.split('\n')
            # Ensure each line ends with \n except the last
            cell['source'] = [line + '\n' if i < len(cell['source']) - 1 else line
                            for i, line in enumerate(cell['source'])]

    # Write back
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)

    return fixes_applied, fixes_list

def main():
    """Fix all advanced notebooks."""
    notebooks_dir = Path('docs/examples/notebooks/advanced')

    notebooks = [
        notebooks_dir / '11_pipeline_deep_dive.ipynb',
        notebooks_dir / '12_advanced_order_management.ipynb',
        notebooks_dir / '13_portfolio_optimization_walk_forward.ipynb',
        notebooks_dir / '14_multi_timeframe_strategies.ipynb',
    ]

    total_fixes = 0
    for notebook_path in notebooks:
        if not notebook_path.exists():
            print(f"❌ Not found: {notebook_path}")
            continue

        print(f"\\n📓 Fixing: {notebook_path.name}")
        fixes_count, fixes = fix_notebook(notebook_path)
        total_fixes += fixes_count

        if fixes_count > 0:
            print(f"   ✅ Applied {fixes_count} fixes:")
            for fix in fixes:
                print(f"      - {fix}")
        else:
            print(f"   ℹ️  No fixes needed")

    print(f"\\n{'='*60}")
    print(f"✨ Total fixes applied: {total_fixes}")
    print(f"{'='*60}")

    return 0 if total_fixes > 0 else 1

if __name__ == '__main__':
    sys.exit(main())
