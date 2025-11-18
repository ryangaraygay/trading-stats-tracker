"""
Tests for AlertConfigManager functionality.
"""

import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest

from alert_config_manager import AlertConfigManager, SessionAlertOverrides


class TestAlertConfigManager:
    """Test AlertConfigManager core functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Clean up any existing active_config.json files first
        active_config_path = Path.home() / ".config" / "trading-stats-tracker" / "alert_configs" / "active_config.json"
        if active_config_path.exists():
            active_config_path.unlink()

        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir)

        # Create test directory structure
        (self.config_dir / "presets").mkdir()
        (self.config_dir / "user").mkdir()
        (self.config_dir / "backups").mkdir()
        (self.config_dir / "schemas").mkdir()

        # Create test config files
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
                "required": ["test_field"]
            },
            "conditions": [
                {
                    "id": "test_condition",
                    "group": "test_group",
                    "when": "test_field >= 10",
                    "level": "WARNING",
                    "message": "Test message",
                    "enabled": True
                }
            ],
            "color_rules": []
        }

        # Write test files
        with open(self.config_dir / "presets" / "test.json", "w") as f:
            json.dump(self.test_config, f)

        # Create schema file
        schema_content = {
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
                            "when": {"type": "string"},
                            "level": {"type": "string"},
                            "message": {"type": "string"},
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

        with open(self.config_dir / "schemas" / "alert_config.schema.json", "w") as f:
            json.dump(schema_content, f)

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_load_config_success(self):
        """Test successful config loading."""
        manager = AlertConfigManager(config_dir=str(self.config_dir))
        config = manager.load_config("test")

        assert config["id"] == "test_config"
        assert config["name"] == "Test Config"
        assert len(config["conditions"]) == 1
        assert config["conditions"][0]["id"] == "test_condition"

    def test_load_config_not_found(self):
        """Test loading non-existent config."""
        manager = AlertConfigManager(config_dir=str(self.config_dir))

        with pytest.raises(FileNotFoundError):
            manager.load_config("nonexistent")

    def test_list_profiles(self):
        """Test profile discovery."""
        manager = AlertConfigManager(config_dir=str(self.config_dir))
        profiles = manager.list_profiles()

        assert len(profiles) == 1
        assert profiles[0]["name"] == "test"
        assert profiles[0]["source"] == "repo_presets"

    def test_create_config_copy(self):
        """Test config copying."""
        manager = AlertConfigManager(config_dir=str(self.config_dir))

        target_path = manager.create_config_copy("test", "test_copy")

        assert target_path.exists()
        assert "test_copy" in str(target_path)

    def test_save_config_with_backup(self):
        """Test config saving with backup creation."""
        manager = AlertConfigManager(config_dir=str(self.config_dir))
        manager.save_config(self.test_config, "test_save")

        # Check that backup was created
        backups = list((self.config_dir / "backups").glob("test_save_*.json"))
        assert len(backups) == 1

        # Check that config was saved
        saved_path = self.config_dir / "user" / "test_save.json"
        assert saved_path.exists()

    def test_schema_validation_failure(self):
        """Test handling of invalid schema."""
        # Create invalid config
        invalid_config = self.test_config.copy()
        del invalid_config["schema_version"]  # Remove required field

        invalid_path = self.config_dir / "presets" / "invalid.json"
        with open(invalid_path, "w") as f:
            json.dump(invalid_config, f)

        manager = AlertConfigManager(config_dir=str(self.config_dir))

        with pytest.raises(ValueError, match="failed schema validation"):
            manager.load_config("invalid")

    @patch('alert_config_manager.jsonschema.validate')
    def test_missing_schema_file(self, mock_validate):
        """Test behavior when schema file is missing."""
        # Remove schema file
        schema_path = self.config_dir / "schemas" / "alert_config.schema.json"
        schema_path.unlink()

        manager = AlertConfigManager(config_dir=str(self.config_dir))

        # Should still load config without validation
        config = manager.load_config("test")
        assert config["id"] == "test_config"

    def test_session_overrides_integration(self):
        """Test session overrides integration."""
        manager = AlertConfigManager(config_dir=str(self.config_dir))
        config = manager.load_config("test")

        # Set override
        manager.session_overrides.set_override("test_condition", {
            "when": "test_field >= 20",
            "level": "CRITICAL"
        })

        # Get active config with overrides
        active_config = manager.get_active_config()

        # Check override was applied
        condition = active_config["conditions"][0]
        assert condition["when"] == "test_field >= 20"
        assert condition["level"] == "CRITICAL"

    def test_validate_profile_does_not_mutate_state(self):
        """validate_profile loads config without changing current_profile_name."""
        manager = AlertConfigManager(config_dir=str(self.config_dir))
        manager.current_profile_name = "original"

        payload = manager.validate_profile("test")

        assert payload["id"] == "test_config"
        assert manager.current_profile_name == "original"


class TestSessionAlertOverrides:
    """Test SessionAlertOverrides functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.overrides = SessionAlertOverrides()

    def test_set_override(self):
        """Test setting overrides."""
        self.overrides.set_override("test_id", {"when": "new_condition", "level": "CRITICAL"})

        conditions = [
            {"id": "test_id", "when": "old_condition", "level": "WARNING"},
            {"id": "other_id", "when": "other_condition", "level": "OK"}
        ]

        result = self.overrides.apply(conditions)

        assert result[0]["when"] == "new_condition"
        assert result[0]["level"] == "CRITICAL"
        assert result[1]["when"] == "other_condition"  # Unchanged

    def test_remove_override(self):
        """Test removing overrides."""
        # Set override
        self.overrides.set_override("test_id", {"when": "new_condition"})
        assert "test_id" in self.overrides.overrides

        # Remove override
        self.overrides.remove_override("test_id")
        assert "test_id" not in self.overrides.overrides

    def test_clear_overrides(self):
        """Test clearing all overrides."""
        # Set multiple overrides
        self.overrides.set_override("test1", {"when": "condition1"})
        self.overrides.set_override("test2", {"when": "condition2"})
        assert len(self.overrides.overrides) == 2

        # Clear all overrides
        self.overrides.clear()
        assert len(self.overrides.overrides) == 0

    def test_apply_no_overrides(self):
        """Test apply with no overrides set."""
        conditions = [{"id": "test", "when": "condition"}]
        result = self.overrides.apply(conditions)

        assert result == conditions  # Should be unchanged

    def test_override_merges(self):
        """Test that overrides merge with existing condition data."""
        self.overrides.set_override("test_id", {"level": "CRITICAL"})

        conditions = [
            {"id": "test_id", "when": "condition", "level": "WARNING", "message": "old"}
        ]

        result = self.overrides.apply(conditions)

        # Should merge override with existing data
        assert result[0]["when"] == "condition"  # Original
        assert result[0]["level"] == "CRITICAL"  # Overridden
        assert result[0]["message"] == "old"     # Original
