#!/usr/bin/env python3
"""
Comprehensive fix script to eliminate ALL hardcoded calculations.
This script aggressively replaces all hardcoded patterns with centralized calls.
"""

import os
import re
from pathlib import Path

def comprehensive_fix():
    """Comprehensive fix for all hardcoded calculations."""
    
    print("🔥 COMPREHENSIVE FIX - ELIMINATING ALL HARDCODED CALCULATIONS")
    
    skip_files = {
        'controllers/gex_calculations.py',
        'controllers/calculation_validator.py',
        'test_calculation_fixes.py',
        'test_ui_consistency.py',
        'verify_single_source.py',
        'fix_hardcoded_calculations.py',
        'comprehensive_fix.py'
    }
    
    fixed_count = 0
    
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
            
            # AGGRESSIVE REPLACEMENT PATTERNS
            
            # Pattern 1: Replace ANY sum(cg) or sum(pg) with centralized call
            content = re.sub(
                r'sum\(.*r\.get\(["\']cg["\'].*for.*r.*in.*\w+\)',
                lambda m: 'calculate_all_aggregates(rows)["total_call_gex"]',
                content,
                flags=re.IGNORECASE
            )
            
            content = re.sub(
                r'sum\(.*r\.get\(["\']pg["\'].*for.*r.*in.*\w+\)',
                lambda m: 'calculate_all_aggregates(rows)["total_put_gex"]',
                content,
                flags=re.IGNORECASE
            )
            
            # Pattern 2: Replace hardcoded gex_ratio calculations
            content = re.sub(
                r'if.*>.*abs.*:.*\n.*round\(.*\/.*\).*\n.*else:.*\n.*round\(.*\/.*\)',
                'calculate_gex_ratio(rows)',
                content,
                flags=re.MULTILINE | re.DOTALL
            )
            
            # Pattern 3: Replace hardcoded sentiment calculations
            content = re.sub(
                r'round\(.*pos_bars.*\/.*len\(.*\).*\*.*100\)',
                'calculate_all_aggregates(rows)["sentiment"]',
                content,
                flags=re.IGNORECASE
            )
            
            # Pattern 4: Replace hardcoded net_gex calculations
            content = re.sub(
                r'sum\(.*r\.get\(["\']net["\'].*for.*r.*in.*\w+\)',
                'calculate_all_aggregates(rows)["net_gex"]',
                content,
                flags=re.IGNORECASE
            )
            
            # Pattern 5: Add centralized import if needed
            if 'calculate_all_aggregates' in content and 'from controllers.gex_calculations import' not in content:
                content = 'from controllers.gex_calculations import calculate_all_aggregates, calculate_gex_ratio\n' + content
            
            # Write back if changed
            if content != original_content:
                with open(py_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                fixed_count += 1
                print(f"   Fixed: {file_str}")
                
        except Exception as e:
            print(f"   Error fixing {file_str}: {e}")
    
    print(f"\n✅ Comprehensive fix completed: {fixed_count} files modified")
    return fixed_count

if __name__ == "__main__":
    comprehensive_fix()
