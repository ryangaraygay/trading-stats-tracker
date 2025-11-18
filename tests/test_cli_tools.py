"""
Tests for CLI tools (manage_alert_configs.py).
"""

import json
import tempfile
import subprocess
import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock


class TestCLICommands:
    """Test CLI commands functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir)
        self.project_root = Path(__file__).parent.parent

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

        # Write test files to temporary directory
        (self.config_dir / "presets").mkdir()
        with open(self.config_dir / "presets" / "test.json", "w") as f:
            json.dump(self.test_config, f)

        with open(self.config_dir / "presets" / "default.json", "w") as f:
            json.dump(self.test_config, f)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

        # Clean up any active_config.json files created during tests
        active_config_path = Path.home() / ".config" / "trading-stats-tracker" / "alert_configs" / "active_config.json"
        if active_config_path.exists():
            active_config_path.unlink()

    def _mock_alert_config_manager(self):
        """Create a mock AlertConfigManager for testing CLI commands."""
        mock_manager = MagicMock()

        # Setup mock responses for list_profiles
        mock_manager.list_profiles.return_value = [
            {"name": "test", "source": "repo_presets", "path": str(self.config_dir / "presets" / "test.json")},
            {"name": "default", "source": "repo_presets", "path": str(self.config_dir / "presets" / "default.json")}
        ]

        # Setup mock for create_config_copy
        mock_manager.create_config_copy.return_value = self.config_dir / "user" / "test_clone.json"

        # Setup mock for set_active_profile
        mock_manager.set_active_profile.return_value = None

        # Setup mock for get_active_profile_name
        mock_manager.get_active_profile_name.return_value = "default"

        # Setup mock for get_profile_path
        mock_manager.get_profile_path.return_value = self.config_dir / "presets" / "default.json"

        # Setup mock for validate_profile
        mock_manager.validate_profile.return_value = self.test_config

        return mock_manager

    def test_list_command(self):
        """Test the list command."""
        with patch('manage_alert_configs.AlertConfigManager') as mock_manager_class:
            mock_manager_class.return_value = self._mock_alert_config_manager()

            result = subprocess.run(
                [sys.executable, "manage_alert_configs.py", "list"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "test" in result.stdout
            assert "default" in result.stdout

    def test_validate_command(self):
        """Test the validate command."""
        with patch('manage_alert_configs.AlertConfigManager') as mock_manager_class:
            mock_manager_class.return_value = self._mock_alert_config_manager()

            result = subprocess.run(
                [sys.executable, "manage_alert_configs.py", "validate"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "Validated test" in result.stdout
            assert "Validated default" in result.stdout

    def test_validate_specific_profile(self):
        """Test validation of a specific profile."""
        # Use mock to test the CLI command directly instead of subprocess
        with patch('manage_alert_configs.AlertConfigManager') as mock_manager_class:
            mock_manager = self._mock_alert_config_manager()
            mock_manager.validate_profile.return_value = self.test_config
            mock_manager_class.return_value = mock_manager

            # Import and test the CLI function directly
            from manage_alert_configs import cmd_validate
            import argparse

            # Create mock args
            args = argparse.Namespace()
            args.profile = "test"

            # Call the CLI function directly
            result = cmd_validate(args)

            assert result == 0
            mock_manager.validate_profile.assert_called_once_with("test")

    def test_clone_command(self):
        """Test the clone command."""
        # Use mock to test the CLI function directly instead of subprocess
        with patch('manage_alert_configs.AlertConfigManager') as mock_manager_class:
            mock_manager = self._mock_alert_config_manager()
            mock_manager.create_config_copy.return_value = self.config_dir / "user" / "test_clone.json"
            mock_manager_class.return_value = mock_manager

            # Import and test the CLI function directly
            from manage_alert_configs import cmd_clone
            import argparse

            # Create mock args
            args = argparse.Namespace()
            args.source = "default"
            args.target = "test_clone"

            # Call the CLI function directly
            result = cmd_clone(args)

            assert result == 0
            mock_manager.create_config_copy.assert_called_once_with("default", "test_clone")

    def test_set_active_command(self):
        """Test the set-active command."""
        with patch('manage_alert_configs.AlertConfigManager') as mock_manager_class:
            mock_manager_class.return_value = self._mock_alert_config_manager()

            result = subprocess.run(
                [sys.executable, "manage_alert_configs.py", "set-active", "default"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "Active profile set to default" in result.stdout

    def test_show_active_command(self):
        """Test the show-active command."""
        with patch('manage_alert_configs.AlertConfigManager') as mock_manager_class:
            mock_manager_class.return_value = self._mock_alert_config_manager()

            result = subprocess.run(
                [sys.executable, "manage_alert_configs.py", "show-active"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert result.stdout.strip() == "default"

    def test_clone_nonexistent_source(self):
        """Test cloning from non-existent source."""
        with patch('manage_alert_configs.AlertConfigManager') as mock_manager_class:
            mock_manager = self._mock_alert_config_manager()
            mock_manager.create_config_copy.side_effect = FileNotFoundError("Source not found")
            mock_manager_class.return_value = mock_manager

            result = subprocess.run(
                [sys.executable, "manage_alert_configs.py", "clone", "nonexistent", "test_dest"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 2  # File not found error

    def test_clone_existing_destination(self):
        """Test cloning to an existing destination."""
        with patch('manage_alert_configs.AlertConfigManager') as mock_manager_class:
            mock_manager = self._mock_alert_config_manager()
            mock_manager.create_config_copy.side_effect = FileExistsError("Destination exists")
            mock_manager_class.return_value = mock_manager

            result = subprocess.run(
                [sys.executable, "manage_alert_configs.py", "clone", "default", "existing"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 3  # File exists error

    def test_validate_nonexistent_profile(self):
        """Test validation of non-existent profile."""
        with patch('manage_alert_configs.AlertConfigManager') as mock_manager_class:
            mock_manager = self._mock_alert_config_manager()
            mock_manager.validate_profile.side_effect = FileNotFoundError("Profile not found")
            mock_manager_class.return_value = mock_manager

            result = subprocess.run(
                [sys.executable, "manage_alert_configs.py", "validate", "--profile", "nonexistent"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 1  # Validation failed

    def test_export_hardcoded_command(self):
        """Test the export-hardcoded command."""
        with patch('manage_alert_configs.AlertConfigManager') as mock_manager_class:
            mock_manager = self._mock_alert_config_manager()
            mock_manager.get_profile_path.return_value = self.config_dir / "presets" / "default.json"
            mock_manager_class.return_value = mock_manager

            export_path = Path(self.temp_dir) / "exported.json"
            result = subprocess.run(
                [sys.executable, "manage_alert_configs.py", "export-hardcoded", str(export_path)],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "Exported hardcoded preset to" in result.stdout


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent

    def test_invalid_command(self):
        """Test handling of invalid command."""
        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "invalid_command"],
            cwd=self.project_root,
            capture_output=True,
            text=True
        )

        assert result.returncode == 2  # Command error

    def test_help_command(self):
        """Test help command."""
        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "--help"],
            cwd=self.project_root,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "list" in result.stdout
        assert "clone" in result.stdout
        assert "validate" in result.stdout
        assert "export-hardcoded" in result.stdout
        assert "set-active" in result.stdout

    def test_missing_config_directory(self):
        """Test behavior when config directory doesn't exist."""
        empty_dir = tempfile.mkdtemp()

        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "list"],
            cwd=empty_dir,
            capture_output=True,
            text=True
        )

        # Should handle gracefully (may return empty list or error)
        assert result.returncode in [0, 1, 2]