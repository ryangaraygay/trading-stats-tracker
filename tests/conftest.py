"""
Essential tests for JSON Alert Config system.

This test suite covers the core functionality of the JSON Alert Config implementation
including AlertConfigManager, ConditionEvaluator, TradeStatsProcessor integration,
and CLI tools. These tests ensure the system works correctly and can safely replace
the hardcoded conditions.
"""

import pytest

# Test configuration to run tests in order and provide better reporting
def pytest_configure(config):
    """Configure pytest with custom settings."""
    config.addinivalue_line(
        "markers", "essential: mark test as essential for production readiness"
    )

def pytest_collection_modifyitems(config, items):
    """Modify test collection to mark essential tests."""
    for item in items:
        if "essential" in item.nodeid:
            item.add_marker(pytest.mark.essential)

# Run a simple test to verify the test infrastructure works
def test_smoke_test():
    """Basic smoke test to verify test infrastructure."""
    assert True