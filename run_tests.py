#!/usr/bin/env python3
"""
Test runner for JSON Alert Config essential tests.

This script runs the essential tests for the JSON Alert Config system
to verify that the core functionality works correctly.
"""

import subprocess
import sys
from pathlib import Path


def run_tests():
    """Run the essential tests for JSON Alert Config."""
    print("🧪 Running Essential JSON Alert Config Tests")
    print("=" * 50)
    
    project_root = Path(__file__).parent
    test_files = [
        "tests/test_alert_config_manager.py",
        "tests/test_condition_evaluator.py", 
        "tests/test_integration.py",
        "tests/test_cli_tools.py"
    ]
    
    all_passed = True
    
    for test_file in test_files:
        print(f"\n📁 Testing {test_file}...")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "-v"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ {test_file} - All tests passed")
        else:
            print(f"❌ {test_file} - Some tests failed")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All essential tests PASSED!")
        print("The JSON Alert Config system is working correctly.")
        return 0
    else:
        print("💥 Some tests FAILED!")
        print("Please check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())