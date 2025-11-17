"""
Tests for TradeStatsProcessor integration with JSON Alert Config.
"""

import json
import tempfile
from unittest.mock import patch, MagicMock
import pytest

from trade_stats_processor import TradeStatsProcessor
from alert_config_manager import AlertConfigManager, ConditionEvaluator


class TestTradeStatsProcessorIntegration:
    """Test TradeStatsProcessor integration with JSON Alert Config."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        # Mock config
        self.mock_config = MagicMock()
        self.mock_config.get_alert_duration.return_value = 5
        self.mock_config.get_min_interval_secs.return_value = 0
        self.mock_config.directory_path = self.temp_dir

        # Test alert context (all required fields)
        self.test_context = {
            "completed_trades": 25,
            "total_profit_or_loss": -1500,
            "profit_factor": 0.8,
            "win_rate": 20,
            "directional_bias_extramsg": "Test bias message",
            "streak_tracker": MagicMock(streak=-5),
            "streak_tracker.streak": -5,
            "loss_max_size": 8,
            "current_drawdown": -2500,
            "loss_scaled_count": 4,
            "open_position_size": 2,
            "win_avg_secs_vs_loss_avg_secs": 45
        }

        # Test config that matches some conditions
        self.test_config = {
            "schema_version": "1.0",
            "id": "test_config",
            "name": "Test Config",
            "description": "Test configuration",
            "metadata": {
                "created_by": "test",
                "created_at": "2024-01-01T00:00:00Z",
                "source": "repo"
            },
            "context_fields": {
                "required": list(self.test_context.keys())
            },
            "conditions": [
                {
                    "id": "trade-count-warning",
                    "group": "trade_count",
                    "when": "completed_trades >= 20",
                    "level": "WARNING",
                    "message": "High trade count",
                    "extra_message": "{completed_trades}",
                    "enabled": True
                },
                {
                    "id": "pnl-warning",
                    "group": "profit_loss",
                    "when": "total_profit_or_loss < -1000",
                    "level": "WARNING",
                    "message": "Significant loss",
                    "extra_message": "{total_profit_or_loss:+,}",
                    "enabled": True
                },
                {
                    "id": "winrate-caution",
                    "group": "win_rate",
                    "when": "win_rate <= 25",
                    "level": "CAUTION",
                    "message": "Low win rate",
                    "extra_message": "{directional_bias_extramsg}",
                    "enabled": True
                },
                {
                    "id": "drawdown-critical",
                    "group": "drawdown",
                    "when": "current_drawdown < -2000",
                    "level": "CRITICAL",
                    "message": "Deep drawdown",
                    "extra_message": "{current_drawdown:+,}",
                    "enabled": True
                }
            ],
            "color_rules": []
        }

    def test_initialize_alert_config_manager_success(self):
        """Test successful initialization of alert config manager."""
        with patch('trade_stats_processor.AlertConfigManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            processor = TradeStatsProcessor(self.mock_config)

            assert processor.alert_config_manager == mock_manager
            mock_manager_class.assert_called_once()
            mock_manager.load_config.assert_called_once()

    def test_initialize_alert_config_manager_failure(self):
        """Test handling of alert config manager initialization failure."""
        with patch('trade_stats_processor.AlertConfigManager') as mock_manager_class:
            mock_manager_class.side_effect = Exception("Config loading failed")

            processor = TradeStatsProcessor(self.mock_config)

            assert processor.alert_config_manager is None

    def test_evaluate_alerts_with_json_config(self):
        """Test alert evaluation with JSON config."""
        processor = TradeStatsProcessor.__new__(TradeStatsProcessor)
        processor.alert_config_manager = MagicMock()

        # Mock the config manager to return our test config
        processor.alert_config_manager.get_active_config.return_value = self.test_config

        # Mock ConditionEvaluator
        with patch('trade_stats_processor.ConditionEvaluator') as mock_evaluator_class:
            mock_evaluator = MagicMock()
            mock_evaluator_class.return_value = mock_evaluator
            mock_evaluator.evaluate.return_value = [
                {
                    "id": "trade-count-warning",
                    "group": "trade_count",
                    "message": "High trade count",
                    "extra_message": "25",
                    "level": "WARNING"
                }
            ]

            results = processor._evaluate_alerts(self.test_context)

            # Verify evaluator was created and called
            mock_evaluator_class.assert_called_once_with(self.test_config)
            mock_evaluator.evaluate.assert_called_once_with(self.test_context)
            assert len(results) == 1

    def test_evaluate_alerts_fallback_to_legacy(self):
        """Test fallback to legacy alerts when JSON config fails."""
        processor = TradeStatsProcessor.__new__(TradeStatsProcessor)
        processor.alert_config_manager = MagicMock()
        processor.alert_config_manager.get_active_config.side_effect = Exception("JSON failed")

        # Mock the legacy alerts method
        processor._legacy_alerts = MagicMock(return_value=[{"legacy": "alert"}])

        results = processor._evaluate_alerts(self.test_context)

        # Should fall back to legacy alerts
        processor._legacy_alerts.assert_called_once_with(self.test_context)
        assert results == [{"legacy": "alert"}]

    def test_evaluate_alerts_no_config_manager(self):
        """Test behavior when no config manager is available."""
        processor = TradeStatsProcessor.__new__(TradeStatsProcessor)
        processor.alert_config_manager = None

        # Mock the legacy alerts method
        processor._legacy_alerts = MagicMock(return_value=[{"legacy": "alert"}])

        results = processor._evaluate_alerts(self.test_context)

        # Should use legacy alerts
        processor._legacy_alerts.assert_called_once_with(self.test_context)
        assert results == [{"legacy": "alert"}]

    def test_legacy_alerts_basic_functionality(self):
        """Test basic functionality of legacy alerts."""
        processor = TradeStatsProcessor.__new__(TradeStatsProcessor)
        processor.alert_config_manager = None

        # Test context that should trigger some legacy conditions
        legacy_context = {
            "completed_trades": 35,  # Should trigger trade count critical
            "total_profit_or_loss": -1500,  # Should trigger P&L warning
            "profit_factor": 0.8,
            "win_rate": 20,
            "loss_scaled_count": 6,
            "loss_max_size": 8,
            "current_drawdown": -2500,
            "directional_bias_extramsg": "Test bias",
            "streak_tracker": MagicMock(streak=-8, get_extra_msg=MagicMock(return_value="Test"))
        }

        # This should return alerts without raising exceptions
        alerts = processor._legacy_alerts(legacy_context)
        assert isinstance(alerts, list)

    def test_context_field_coverage(self):
        """Test that all required context fields are provided."""
        processor = TradeStatsProcessor.__new__(TradeStatsProcessor)

        # Mock a config that requires specific fields
        config_with_requirements = {
            "context_fields": {
                "required": ["completed_trades", "total_profit_or_loss", "missing_field"]
            },
            "conditions": []
        }

        processor.alert_config_manager = MagicMock()
        processor.alert_config_manager.get_active_config.return_value = config_with_requirements

        # Test context missing a required field
        incomplete_context = {
            "completed_trades": 10,
            "total_profit_or_loss": 100
            # missing_field is missing
        }

        processor._legacy_alerts = MagicMock(return_value=[])

        # Should NOT fall back to legacy alerts - ConditionEvaluator handles missing fields gracefully
        # The evaluation will just not match conditions that reference missing fields
        results = processor._evaluate_alerts(incomplete_context)
        # Since the config is valid and the manager works, it should NOT call legacy alerts
        processor._legacy_alerts.assert_not_called()

    def test_get_stats_includes_context_fields(self):
        """Test that get_stats method provides all required context fields."""
        # This test would require setting up file data and testing the full get_stats flow
        # For now, we'll verify that the method signature and basic structure exist
        processor = TradeStatsProcessor(self.mock_config)

        # Verify the method exists and can be called
        assert hasattr(processor, 'get_stats')
        assert callable(getattr(processor, 'get_stats'))


class TestAlertMessageCreation:
    """Test AlertMessage creation from evaluator output."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = MagicMock()
        self.mock_config.get_alert_duration.return_value = 5
        self.mock_config.get_min_interval_secs.return_value = 0

    def test_alert_message_creation_from_evaluator_result(self):
        """Test creating AlertMessage from evaluator results."""
        from alert_message import AlertMessage
        from concern_level import ConcernLevel

        # Simulate the alert processing logic from TradeStatsProcessor
        evaluator_results = [
            {
                "message": "High trade count",
                "level": ConcernLevel.WARNING,
                "extra_message": "25"
            },
            {
                "message": "Significant loss",
                "level": ConcernLevel.CRITICAL,
                "extra_message": "-1500"
            }
        ]

        # Simulate the alert creation logic
        alerts = []
        for match in evaluator_results:
            message = match.get("message", "")
            level = match.get("level", ConcernLevel.DEFAULT)
            extra = match.get("extra_message", "")

            if not message:
                continue

            alert = AlertMessage(
                message,
                "test_account",
                self.mock_config.get_alert_duration(level),
                self.mock_config.get_min_interval_secs(level),
                level,
                extra
            )
            alerts.append(alert)

        # Verify alerts were created correctly
        assert len(alerts) == 2
        assert alerts[0].message == "High trade count"
        assert alerts[0].level == ConcernLevel.WARNING
        assert alerts[0].extra_msg == "25"
        assert alerts[1].message == "Significant loss"
        assert alerts[1].level == ConcernLevel.CRITICAL
        assert alerts[1].extra_msg == "-1500"