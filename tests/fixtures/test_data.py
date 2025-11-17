"""
Test fixtures for JSON Alert Config tests.
"""

# Valid test configuration
VALID_CONFIG = {
    "schema_version": "1.0",
    "id": "test_config",
    "name": "Test Config",
    "description": "Test configuration for unit tests",
    "metadata": {
        "created_by": "test",
        "created_at": "2024-01-01T00:00:00Z",
        "source": "repo"
    },
    "context_fields": {
        "required": [
            "completed_trades",
            "total_profit_or_loss",
            "profit_factor",
            "win_rate",
            "directional_bias_extramsg",
            "streak_tracker.streak",
            "loss_max_size",
            "current_drawdown",
            "loss_scaled_count",
            "open_position_size",
            "win_avg_secs_vs_loss_avg_secs"
        ]
    },
    "conditions": [
        {
            "id": "trade-count-critical",
            "group": "trade_count",
            "label": "Trade Count Critical",
            "when": "completed_trades >= 30",
            "level": "CRITICAL",
            "message": "Stop. Maximum trades for the day reached.",
            "extra_message": "{completed_trades}",
            "throttle_secs": 0,
            "enabled": True
        },
        {
            "id": "trade-count-warning",
            "group": "trade_count",
            "label": "Trade Count Warning",
            "when": "completed_trades >= 20",
            "level": "WARNING",
            "message": "Wind down. You've reached your trade count goal.",
            "extra_message": "{completed_trades}",
            "enabled": True
        },
        {
            "id": "pnl-critical",
            "group": "profit_loss",
            "label": "P&L Critical",
            "when": "total_profit_or_loss < -2100",
            "level": "CRITICAL",
            "message": "Stop. Protect your capital.",
            "extra_message": "{total_profit_or_loss:+,}",
            "enabled": True
        },
        {
            "id": "winrate-warning",
            "group": "win_rate",
            "label": "Low Win Rate",
            "when": "win_rate <= 25 and profit_factor < 1.0 and completed_trades >= 10",
            "level": "WARNING",
            "message": "Reset. Win Rate very low.",
            "extra_message": "{directional_bias_extramsg}",
            "enabled": True
        },
        {
            "id": "losing-streak-critical",
            "group": "losing_streak",
            "label": "Deep Losing Streak",
            "when": "streak_tracker.streak <= -7",
            "level": "CRITICAL",
            "message": "Stop now. Protect the version of you that trades well tomorrow.",
            "enabled": True
        },
        {
            "id": "loss-max-warning",
            "group": "loss_max_size",
            "label": "Max Loss Size Warning",
            "when": "loss_max_size >= 10",
            "level": "WARNING",
            "message": "Reset. Size down.",
            "enabled": True
        }
    ],
    "color_rules": [
        {
            "metric": "win_rate",
            "rules": [
                {"when": "win_rate <= 25", "color": "#b00020"},
                {"when": "win_rate <= 40", "color": "#f9a825"}
            ]
        }
    ]
}

# Invalid configuration (missing required fields)
INVALID_CONFIG = {
    "id": "invalid_config",
    "name": "Invalid Config",
    # Missing schema_version, metadata, context_fields, conditions
}

# Test alert context with all required fields
TEST_CONTEXT = {
    "completed_trades": 25,
    "total_profit_or_loss": -1500,
    "profit_factor": 0.8,
    "win_rate": 20,
    "directional_bias_extramsg": "Test bias message",
    "streak_tracker": None,  # Will be mocked
    "streak_tracker.streak": -5,
    "loss_max_size": 8,
    "current_drawdown": -2500,
    "loss_scaled_count": 4,
    "open_position_size": 2,
    "win_avg_secs_vs_loss_avg_secs": 45
}

# Alert context that triggers multiple conditions
TRIGGERING_CONTEXT = {
    "completed_trades": 35,  # Triggers trade-count-critical
    "total_profit_or_loss": -2500,  # Triggers pnl-critical
    "profit_factor": 0.5,  # Part of winrate-warning condition
    "win_rate": 20,  # Part of winrate-warning condition
    "directional_bias_extramsg": "Bias message",
    "streak_tracker": None,
    "streak_tracker.streak": -8,  # Triggers losing-streak-critical
    "loss_max_size": 12,  # Triggers loss-max-warning
    "current_drawdown": -3500,
    "loss_scaled_count": 6,
    "open_position_size": 4,
    "win_avg_secs_vs_loss_avg_secs": 30
}

# Alert context that triggers no conditions
NON_TRIGGERING_CONTEXT = {
    "completed_trades": 5,
    "total_profit_or_loss": 500,
    "profit_factor": 2.0,
    "win_rate": 60,
    "directional_bias_extramsg": "",
    "streak_tracker": None,
    "streak_tracker.streak": 2,
    "loss_max_size": 2,
    "current_drawdown": -100,
    "loss_scaled_count": 0,
    "open_position_size": 0,
    "win_avg_secs_vs_loss_avg_secs": 120
}

# JSON Schema for validation
ALERT_CONFIG_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "schema_version": {"type": "string"},
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "metadata": {
            "type": "object",
            "properties": {
                "created_by": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
                "source": {"type": "string", "enum": ["repo", "user", "session"]}
            },
            "required": ["created_by", "created_at", "source"],
            "additionalProperties": False
        },
        "context_fields": {
            "type": "object",
            "properties": {
                "required": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1
                }
            },
            "required": ["required"],
            "additionalProperties": False
        },
        "conditions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "group": {"type": "string"},
                    "label": {"type": "string"},
                    "when": {"type": "string"},
                    "primary_field": {"type": "string"},
                    "threshold": {"type": ["number", "integer"]},
                    "operator": {"type": "string"},
                    "additional_conditions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "operator": {"type": "string"},
                                "value": {}
                            },
                            "required": ["field", "operator", "value"],
                            "additionalProperties": False
                        }
                    },
                    "abs_value": {"type": "boolean"},
                    "comparison_field": {"type": "string"},
                    "level": {"type": "string"},
                    "message": {"type": "string"},
                    "extra_message": {"type": "string"},
                    "throttle_secs": {"type": "number"},
                    "enabled": {"type": "boolean"}
                },
                "required": ["id", "group", "when", "level"],
                "additionalProperties": False
            }
        },
        "color_rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string"},
                    "rules": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "when": {"type": "string"},
                                "color": {"type": "string"}
                            },
                            "required": ["when", "color"],
                            "additionalProperties": False
                        }
                    }
                },
                "required": ["metric", "rules"],
                "additionalProperties": False
            }
        }
    },
    "required": ["schema_version", "id", "name", "metadata", "context_fields", "conditions"],
    "additionalProperties": False
}