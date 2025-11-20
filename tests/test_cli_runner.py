#!/usr/bin/env python3
"""
Simple test runner for CLI tools that can be used in pytest.
"""

import subprocess
import sys
from pathlib import Path


def run_cli_test(command_args, cwd=None, expected_returncode=0):
    """
    Run a CLI command and return the result.
    
    Args:
        command_args: List of command arguments
        cwd: Working directory (defaults to project root)
        expected_returncode: Expected return code
    
    Returns:
        tuple: (success: bool, result: subprocess.CompletedProcess)
    """
    if cwd is None:
        # Default to project root (where manage_alert_configs.py is located)
        cwd = Path(__file__).parent.parent
    
    try:
        result = subprocess.run(
            [sys.executable] + command_args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10  # Prevent hanging
        )
        
        success = result.returncode == expected_returncode
        return success, result
    
    except subprocess.TimeoutExpired:
        return False, None
    except Exception as e:
        return False, subprocess.CompletedProcess(
            args=command_args,
            returncode=999,
            stdout="",
            stderr=str(e)
        )


if __name__ == "__main__":
    # Simple CLI for testing
    import sys
    if len(sys.argv) < 2:
        print("Usage: python test_cli_runner.py <command> [args...]")
        sys.exit(1)
    
    command = sys.argv[1:]
    success, result = run_cli_test(command)
    
    if success:
        print("✅ Command succeeded")
        if result and result.stdout:
            print("STDOUT:", result.stdout)
    else:
        print("❌ Command failed")
        print("Return code:", result.returncode if result else "timeout")
        if result and result.stderr:
            print("STDERR:", result.stderr)
    
    sys.exit(0 if success else 1)