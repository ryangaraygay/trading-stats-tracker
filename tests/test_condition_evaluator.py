"""
Tests for ConditionEvaluator functionality.
"""

import json
import tempfile
from unittest.mock import patch
import pytest

from alert_config_manager import ConditionEvaluator
from concern_level import ConcernLevel


class TestConditionEvaluator:
    """Test ConditionEvaluator core functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_config = {
            "conditions": [
                {
                    "id": "test_critical",
                    "group": "test_group",
                    "when": "test_field >= 10",
                    "level": "CRITICAL",
                    "message": "Critical message",
                    "extra_message": "Critical extra",
                    "enabled": True
                },
                {
                    "id": "test_warning",
                    "group": "test_group",
                    "when": "test_field >= 5",
                    "level": "WARNING",
                    "message": "Warning message",
                    "extra_message": "Warning extra",
                    "enabled": True
                },
                {
                    "id": "test_disabled",
                    "group": "test_group",
                    "when": "test_field >= 1",
                    "level": "CAUTION",
                    "message": "Disabled message",
                    "enabled": "false"  # Should be boolean, test type conversion
                },
                {
                    "id": "test_group2",
                    "group": "different_group",
                    "when": "other_field <= 0",
                    "level": "OK",
                    "message": "Different group",
                    "enabled": True
                }
            ],
            "color_rules": []
        }

    def test_basic_evaluation(self):
        """Test basic condition evaluation."""
        evaluator = ConditionEvaluator(self.test_config)

        context = {"test_field": 15}
        results = evaluator.evaluate(context)

        # Should match first condition (group short-circuit)
        # Only test_critical should match since test_group2 has missing other_field
        assert len(results) == 1  # Only test_critical should match
        assert results[0]["id"] == "test_critical"
        assert results[0]["level"] == ConcernLevel.CRITICAL
        assert results[0]["message"] == "Critical message"
        assert results[0]["extra_message"] == "Critical extra"

    def test_group_short_circuit(self):
        """Test that first match in group wins."""
        evaluator = ConditionEvaluator(self.test_config)

        context = {"test_field": 15}  # Matches both test_critical and test_warning
        results = evaluator.evaluate(context)

        # Should only get the first match in test_group
        test_group_results = [r for r in results if r["group"] == "test_group"]
        assert len(test_group_results) == 1
        assert test_group_results[0]["id"] == "test_critical"

    def test_disabled_conditions(self):
        """Test that disabled conditions are skipped and edge cases are handled."""
        test_config_with_various_enabled_states = {
            "conditions": [
                {
                    "id": "test_enabled",
                    "group": "test_group1",
                    "when": "test_field >= 1",
                    "level": "WARNING",
                    "message": "Enabled message",
                    "enabled": True
                },
                {
                    "id": "test_disabled_boolean",
                    "group": "test_group2",
                    "when": "test_field >= 2",
                    "level": "CAUTION",
                    "message": "Disabled boolean message",
                    "enabled": False
                },
                {
                    "id": "test_enabled_missing",
                    "group": "test_group3",
                    "when": "test_field >= 3",
                    "level": "OK",
                    "message": "Missing enabled field",
                    # Note: no "enabled" field - should default to enabled
                },
                {
                    "id": "test_enabled_none",
                    "group": "test_group4",
                    "when": "test_field >= 4",
                    "level": "CRITICAL",
                    "message": "Enabled None",
                    "enabled": None
                },
                {
                    "id": "test_enabled_string",
                    "group": "test_group5",
                    "when": "test_field >= 5",
                    "level": "WARNING",
                    "message": "Enabled string",
                    "enabled": "false"
                },
                {
                    "id": "test_enabled_number",
                    "group": "test_group6",
                    "when": "test_field >= 6",
                    "level": "CAUTION",
                    "message": "Enabled number",
                    "enabled": 0
                }
            ]
        }

        evaluator = ConditionEvaluator(test_config_with_various_enabled_states)

        # Test with high value that would match all conditions
        context = {"test_field": 10}
        results = evaluator.evaluate(context)

        # Should only match enabled conditions
        # enabled=True: test_enabled (included)
        # enabled=False: test_disabled_boolean (excluded)
        # enabled missing: test_enabled_missing (included - defaults to True)
        # enabled=None: test_enabled_none (excluded - falsy)
        # enabled="false": test_enabled_string (included - non-empty string is truthy)
        # enabled=0: test_enabled_number (excluded - falsy)

        result_ids = [r["id"] for r in results]

        # Should include: test_enabled, test_enabled_missing, test_enabled_string
        assert "test_enabled" in result_ids
        assert "test_enabled_missing" in result_ids
        assert "test_enabled_string" in result_ids

        # Should NOT include disabled conditions
        assert "test_disabled_boolean" not in result_ids
        assert "test_enabled_none" not in result_ids
        assert "test_enabled_number" not in result_ids

        # Should have exactly 3 results
        assert len(results) == 3

    def test_multiple_groups(self):
        """Test evaluation across multiple groups."""
        evaluator = ConditionEvaluator(self.test_config)

        context = {
            "test_field": 15,
            "other_field": -5
        }
        results = evaluator.evaluate(context)

        # Should get one result from each group
        assert len(results) == 2

        group_names = [r["group"] for r in results]
        assert "test_group" in group_names
        assert "different_group" in group_names

    def test_no_matches(self):
        """Test when no conditions match."""
        evaluator = ConditionEvaluator(self.test_config)

        context = {"test_field": 0, "other_field": 5}
        results = evaluator.evaluate(context)

        assert len(results) == 0

    def test_invalid_expression(self):
        """Test handling of invalid expressions."""
        config_with_invalid = {
            "conditions": [
                {
                    "id": "invalid_condition",
                    "group": "test_group",
                    "when": "invalid_syntax ==",
                    "level": "WARNING",
                    "message": "Test message",
                    "enabled": True
                }
            ]
        }

        evaluator = ConditionEvaluator(config_with_invalid)

        context = {"test_field": 10}
        # Should not raise exception, should return empty results
        results = evaluator.evaluate(context)
        assert len(results) == 0

    def test_expression_with_missing_context(self):
        """Test expression evaluation with missing context variables."""
        evaluator = ConditionEvaluator(self.test_config)

        context = {}  # Missing test_field
        results = evaluator.evaluate(context)

        # Should not match any conditions due to missing context
        assert len(results) == 0

    def test_unknown_concern_level(self):
        """Test handling of unknown concern levels."""
        config_with_unknown_level = {
            "conditions": [
                {
                    "id": "unknown_level",
                    "group": "test_group",
                    "when": "test_field >= 10",
                    "level": "UNKNOWN_LEVEL",
                    "message": "Test message",
                    "enabled": True
                }
            ]
        }

        evaluator = ConditionEvaluator(config_with_unknown_level)

        context = {"test_field": 15}
        results = evaluator.evaluate(context)

        # Should default to DEFAULT level
        assert len(results) == 1
        assert results[0]["level"] == ConcernLevel.DEFAULT

    def test_empty_conditions(self):
        """Test with empty conditions list."""
        evaluator = ConditionEvaluator({"conditions": [], "color_rules": []})

        context = {"test_field": 10}
        results = evaluator.evaluate(context)

        assert len(results) == 0

    def test_throttle_secs_handling(self):
        """Test that throttle_secs is properly handled."""
        config_with_throttle = {
            "conditions": [
                {
                    "id": "throttle_test",
                    "group": "test_group",
                    "when": "test_field >= 10",
                    "level": "WARNING",
                    "message": "Test message",
                    "throttle_secs": 300,
                    "enabled": True
                }
            ]
        }

        evaluator = ConditionEvaluator(config_with_throttle)

        context = {"test_field": 15}
        results = evaluator.evaluate(context)

        assert len(results) == 1
        assert results[0]["throttle_secs"] == 300

    def test_expression_with_complex_logic(self):
        """Test complex boolean expressions."""
        complex_config = {
            "conditions": [
                {
                    "id": "complex_condition",
                    "group": "test_group",
                    "when": "test_field >= 10 and other_field < 5 or third_field == 'special'",
                    "level": "CRITICAL",
                    "message": "Complex condition met",
                    "enabled": True
                }
            ]
        }

        evaluator = ConditionEvaluator(complex_config)

        # Test complex expression that should evaluate to True
        context = {
            "test_field": 15,
            "other_field": 2,
            "third_field": "not_special"
        }
        results = evaluator.evaluate(context)

        assert len(results) == 1
        assert results[0]["message"] == "Complex condition met"

    def test_safe_globals_usage(self):
        """Test that safe globals are used for evaluation."""
        config_with_safe_funcs = {
            "conditions": [
                {
                    "id": "safe_funcs",
                    "group": "test_group",
                    "when": "abs(test_field) >= 10",
                    "level": "WARNING",
                    "message": "Safe function test",
                    "enabled": True
                }
            ]
        }

        evaluator = ConditionEvaluator(config_with_safe_funcs)

        context = {"test_field": -15}
        results = evaluator.evaluate(context)

        # Should work with abs() function
        assert len(results) == 1
        assert results[0]["message"] == "Safe function test"