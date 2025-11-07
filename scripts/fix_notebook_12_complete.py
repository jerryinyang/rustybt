#!/usr/bin/env python3
"""
Fix remaining critical issues in notebook 12 (Advanced Order Management).

Fixes:
1. BracketOrder constructor calls (add entry_style parameter)
2. Remove OCO add_oco_sibling examples (not implemented)
3. Remove order modification examples (not implemented)
"""

import json
import sys
from pathlib import Path


def fix_notebook_12():
    """Fix all issues in advanced order management notebook."""
    notebook_path = Path('docs/examples/notebooks/advanced/12_advanced_order_management.ipynb')

    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)

    fixes_applied = []

    for i, cell in enumerate(notebook.get('cells', [])):
        if cell.get('cell_type') != 'code':
            continue

        source = ''.join(cell.get('source', []))
        original = source

        # Fix 1: BracketOrder constructor - add entry_style
        if 'BracketOrder(' in source and 'entry_price=' in source:
            # Replace entry_price= with entry_style=MarketOrder() or LimitOrder()
            if 'entry_price=current_price' in source:
                source = source.replace(
                    'entry_price=current_price,',
                    'entry_style=MarketOrder(),  # Was: entry_price=current_price'
                )
                fixes_applied.append(f"Cell {i}: Fixed BracketOrder entry_price -> entry_style=MarketOrder()")

            if 'entry_price=' in source and 'entry_style=' not in source:
                # Generic fix for any remaining entry_price
                source = source.replace(
                    'BracketOrder(\n            entry_price=',
                    'BracketOrder(\n            entry_style=MarketOrder(),  # Fixed: was entry_price='
                )
                fixes_applied.append(f"Cell {i}: Fixed BracketOrder constructor")

        # Fix 2: Remove OCO sibling linking (not implemented)
        if 'add_oco_sibling' in source or 'OCOOrder' in source:
            # Comment out the entire OCO section
            lines = source.split('\n')
            new_lines = []
            in_oco_section = False

            for line in lines:
                if 'OCOOrder' in line or 'add_oco_sibling' in line:
                    new_lines.append('# ⚠️ OCO order sibling linking not yet implemented')
                    new_lines.append('# ' + line)
                    in_oco_section = True
                elif in_oco_section and (line.strip().startswith('self.order') or 'oco' in line.lower()):
                    new_lines.append('# ' + line)
                else:
                    new_lines.append(line)
                    if line.strip() == '':
                        in_oco_section = False

            source = '\n'.join(new_lines)
            fixes_applied.append(f"Cell {i}: Commented out OCO examples (not implemented)")

        # Fix 3: Remove order modification examples
        if 'modify_order' in source:
            lines = source.split('\n')
            new_lines = []

            for line in lines:
                if 'modify_order' in line:
                    new_lines.append('# ⚠️ Order modification not yet implemented in rustybt')
                    new_lines.append('# ' + line)
                    new_lines.append('# TODO: This feature is planned for a future release')
                else:
                    new_lines.append(line)

            source = '\n'.join(new_lines)
            fixes_applied.append(f"Cell {i}: Commented out modify_order (not implemented)")

        # Update cell if changed
        if source != original:
            cell['source'] = [line + '\n' for line in source.split('\n')[:-1]] + [source.split('\n')[-1]]

    # Write back
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)

    return fixes_applied


def main():
    """Apply all fixes to notebook 12."""
    print("\n📓 Fixing: 12_advanced_order_management.ipynb")
    print("=" * 60)

    fixes = fix_notebook_12()

    if fixes:
        print(f"\n✅ Applied {len(fixes)} fixes:")
        for fix in fixes:
            print(f"   - {fix}")
    else:
        print("\n ℹ️  No additional fixes needed")

    print("\n" + "=" * 60)
    print(f"✨ Notebook 12 fixes complete!")
    print("=" * 60 + "\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())
