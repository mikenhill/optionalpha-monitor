#!/usr/bin/env python3
"""
Automated fix script for hardcoded calculations.
This script systematically replaces hardcoded calculations with centralized function calls.
"""

import os
import re
from pathlib import Path

def fix_hardcoded_calculations():
    """Fix hardcoded calculations throughout the codebase."""
    
    print("🔧 FIXING HARDCODED CALCULATIONS...")
    
    # Files to skip
    skip_files = {
        'controllers/gex_calculations.py',
        'controllers/calculation_validator.py',
        'test_calculation_fixes.py',
        'test_ui_consistency.py',
        'verify_single_source.py',
        'fix_hardcoded_calculations.py'
    }
    
    fixed_files = []
    
    for py_file in Path('.').rglob('*.py'):
        if '.venv' in str(py_file) or '__pycache__' in str(py_file):
            continue
            
        file_str = str(py_file)
        if file_str in skip_files:
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Pattern 1: Replace hardcoded sum(cg) and sum(pg) with centralized call
            # Look for patterns like: call_gex = sum(r.get("cg", 0) or 0 for r in rows)
            sum_cg_pattern = r'(\w+)\s*=\s*sum\(r\.get\(["\']cg["\'],\s*0\)\s*or\s*0\s+for\s+r\s+in\s+(\w+)\)'
            content = re.sub(sum_cg_pattern, r'# Use centralized calculation\nfrom controllers.gex_calculations import calculate_all_aggregates\n\1 = calculate_all_aggregates(\2)["total_call_gex"]', content)
            
            sum_pg_pattern = r'(\w+)\s*=\s*sum\(r\.get\(["\']pg["\'],\s*0\)\s*or\s*0\s+for\s+r\s+in\s+(\w+)\)'
            content = re.sub(sum_pg_pattern, r'# Use centralized calculation\nfrom controllers.gex_calculations import calculate_all_aggregates\n\1 = calculate_all_aggregates(\2)["total_put_gex"]', content)
            
            # Pattern 2: Replace hardcoded net_gex calculations
            net_gex_pattern = r'(\w+)\s*=\s*(\w+)\s*-\s*(\w+)'
            # Only replace if it looks like call_gex - put_gex
            if 'call_gex' in content and 'put_gex' in content:
                content = re.sub(net_gex_pattern, r'\1 = calculate_all_aggregates(rows)["net_gex"]', content)
            
            # Pattern 3: Replace hardcoded sentiment calculations
            sentiment_pattern = r'(\w+)\s*=\s*round\(\s*pos_bars\s*/\s*len\(\w+\)\s*\*\s*100\)'
            content = re.sub(sentiment_pattern, r'\1 = calculate_all_aggregates(rows)["sentiment"]', content)
            
            # Pattern 4: Replace hardcoded gex_ratio calculations
            ratio_pattern1 = r'if\s+(\w+)\s*>\s*(\w+):\s*\n\s*(\w+)\s*=\s*round\(\s*\1\s*/\s*\2.*?\)\s*\n\s*else:\s*\n\s*(\w+)\s*=\s*round\(\s*-\s*\2\s*/\s*\1.*?\)'
            content = re.sub(ratio_pattern1, r'\3 = calculate_all_aggregates(rows)["gex_ratio"]', content, flags=re.MULTILINE | re.DOTALL)
            
            # Write back if changed
            if content != original_content:
                with open(py_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                fixed_files.append(file_str)
                print(f"   Fixed: {file_str}")
                
        except Exception as e:
            print(f"   Error fixing {file_str}: {e}")
    
    print(f"\n✅ Fixed {len(fixed_files)} files")
    return fixed_files

if __name__ == "__main__":
    fix_hardcoded_calculations()
