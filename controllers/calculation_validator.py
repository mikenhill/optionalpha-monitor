"""
STRICT CALCULATION VALIDATOR
============================

This module enforces the single source of truth principle.
The app will CRASH catastrophically if any hardcoded calculations are detected.
NO EXCEPTIONS - this ensures immediate detection of obsolete code.
"""

import os
import re
import sys
import traceback
from pathlib import Path

class CalculationViolationError(Exception):
    """Raised when hardcoded calculations are detected."""
    pass

def validate_single_source_of_truth():
    """
    Validate that ONLY centralized calculation functions exist.
    
    CRASHES the app immediately if any hardcoded calculations are found.
    This is intentional - we want catastrophic failure for obsolete code.
    """
    
    print("🔍 VALIDATING SINGLE SOURCE OF TRUTH...")
    
    # Patterns that indicate hardcoded calculations - ZERO TOLERANCE
    hardcoded_patterns = [
        r'sum\(.*cg.*\)',  # Hardcoded call GEX sum
        r'sum\(.*pg.*\)',  # Hardcoded put GEX sum
        r'sum\(.*total.*\)',  # Hardcoded total sum
        r'total_call_gex\s*=',  # Hardcoded total_call_gex assignment
        r'total_put_gex\s*=',  # Hardcoded total_put_gex assignment
        r'gex_ratio\s*=.*sum',  # Hardcoded gex_ratio calculation
        r'net_gex\s*=.*sum',  # Hardcoded net_gex calculation
        r'if.*>.*abs.*:',  # Hardcoded ratio logic
        r'round\(.*\/.*\).*gex',  # Hardcoded GEX ratio rounding
        r'call_gex.*sum',  # Hardcoded call_gex sum
        r'put_gex.*sum',  # Hardcoded put_gex sum
    ]
    
    # Files that are allowed to have calculations (centralized only)
    allowed_files = {
        'controllers/gex_calculations.py',
        'controllers/calculation_validator.py',
        'test_calculation_fixes.py',
        'test_ui_consistency.py',
        'verify_single_source.py'
    }
    
    violations = []
    
    # Scan all Python files
    for py_file in Path('.').rglob('*.py'):
        # Skip virtual environment
        if '.venv' in str(py_file) or '__pycache__' in str(py_file):
            continue
            
        file_str = str(py_file)
        
        # Skip allowed files
        if file_str in allowed_files:
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Check for hardcoded patterns
            for pattern in hardcoded_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    # Get line number and context
                    lines = content[:match.start()].split('\n')
                    line_num = len(lines)
                    line_content = lines[-1] if lines else ""
                    
                    # Skip if it's just a comment or import
                    line_content = line_content.strip()
                    if line_content.startswith('#') or line_content.startswith('"""') or line_content.startswith("'''"):
                        continue
                    
                    violations.append({
                        'file': file_str,
                        'line': line_num,
                        'pattern': pattern,
                        'match': match.group(),
                        'line_content': line_content
                    })
                    
        except Exception as e:
            violations.append({
                'file': file_str,
                'line': 0,
                'pattern': 'FILE_READ_ERROR',
                'match': str(e),
                'line_content': 'Could not read file'
            })
    
    # Check for obsolete snapshot references
    snapshot_violations = scan_for_snapshot_references()
    violations.extend(snapshot_violations)
    
    # CRASH catastrophically if any violations found
    if violations:
        print("\n" + "="*80)
        print("🚨 CATASTROPHIC FAILURE: HARDCODED CALCULATIONS DETECTED")
        print("="*80)
        print("\nThe app will crash to prevent use of obsolete code.")
        print("\nVIOLATIONS FOUND:")
        
        for i, violation in enumerate(violations, 1):
            print(f"\n{i}. {violation['file']}:{violation['line']}")
            print(f"   Pattern: {violation['pattern']}")
            print(f"   Match: {violation['match']}")
            print(f"   Line: {violation['line_content']}")
        
        print("\n" + "="*80)
        print("🔥 CRASHING APP - FIX ALL VIOLATIONS BEFORE RESTARTING")
        print("="*80)
        
        raise CalculationViolationError(f"Found {len(violations)} hardcoded calculation violations")
    
    print("✅ Single source of truth validated - no hardcoded calculations found")

def scan_for_snapshot_references():
    """Scan for obsolete snapshot references."""
    
    snapshot_violations = []
    snapshot_patterns = [
        r'snapshot_dao',
        r'snapshot\s*\.',
        r'FROM\s+snapshot',
        r'UPDATE\s+snapshot',
        r'INSERT\s+INTO\s+snapshot',
        r'_backfill_snapshot',
        r'gex_snapshots',
    ]
    
    for py_file in Path('.').rglob('*.py'):
        if '.venv' in str(py_file) or '__pycache__' in str(py_file):
            continue
            
        # Skip allowed files
        file_str = str(py_file)
        if file_str in {'controllers/calculation_validator.py', 'verify_single_source.py'}:
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            for pattern in snapshot_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    lines = content[:match.start()].split('\n')
                    line_num = len(lines)
                    line_content = lines[-1] if lines else ""
                    
                    # Skip comments and documentation
                    line_content = line_content.strip()
                    if line_content.startswith('#') or line_content.startswith('"""') or line_content.startswith("'''"):
                        continue
                    
                    snapshot_violations.append({
                        'file': file_str,
                        'line': line_num,
                        'pattern': f'OBSOLETE_SNAPSHOT: {pattern}',
                        'match': match.group(),
                        'line_content': line_content
                    })
                    
        except Exception:
            pass  # Ignore file read errors for snapshot scanning
    
    return snapshot_violations

# Auto-validate on import
if __name__ != "__main__":
    # Validate when imported (except when running as script)
    try:
        validate_single_source_of_truth()
    except CalculationViolationError:
        print("\n💥 APP CRASHED DUE TO CALCULATION VIOLATIONS")
        print("   Fix all hardcoded calculations before restarting")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 UNEXPECTED VALIDATION ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Run validation when executed directly
    validate_single_source_of_truth()
