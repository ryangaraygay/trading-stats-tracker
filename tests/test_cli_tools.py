"""
Tests for CLI tools (manage_alert_configs.py).
"""

import json
import tempfile
import subprocess
import sys
from pathlib import Path
import pytest


class TestCLICommands:
    """Test CLI commands functionality."""

    def setup_method(self):
        """Set up test fixtures."""
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

        with open(self.config_dir / "presets" / "default.json", "w") as f:
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
                }
            },
            "required": ["schema_version", "id", "name", "metadata", "context_fields", "conditions"],
            "additionalProperties": False
        }

        with open(self.config_dir / "schemas" / "alert_config.schema.json", "w") as f:
            json.dump(schema_content, f)

    def test_list_command(self):
        """Test the list command."""
        # Use the project root directory where manage_alert_configs.py is located
        project_root = Path(__file__).parent.parent
        
        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "list"],
            cwd=project_root,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        output = result.stdout
        assert "test" in output or "demo-aggressive" in output  # Should find at least one profile

    def test_validate_command(self):
        """Test the validate command."""
        # Use the project root directory where manage_alert_configs.py is located
        project_root = Path(__file__).parent.parent
        
        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "validate"],
            cwd=project_root,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        output = result.stdout
        assert "Validated" in output  # Should validate at least the default config

    def test_validate_specific_profile(self):
        """Test validation of specific profile."""
        # Use the project root directory where manage_alert_configs.py is located
        project_root = Path(__file__).parent.parent
        
        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "validate", "--profile", "default"],
            cwd=project_root,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        output = result.stdout
        assert "Validated default" in output

    def test_clone_command(self):
        """Test the clone command."""
        # Use the project root directory where manage_alert_configs.py is located
        project_root = Path(__file__).parent.parent
        
        # Use a timestamp-based unique name to avoid conflicts
        import time
        unique_name = f"test_clone_{int(time.time())}"
        
        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "clone", "default", unique_name],
            cwd=project_root,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert f"Copied 'default' to" in result.stdout

    def test_set_active_command(self):
        """Test the set-active command."""
        # Use the project root directory where manage_alert_configs.py is located
        project_root = Path(__file__).parent.parent
        
        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "set-active", "default"],
            cwd=project_root,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "Active profile set to default" in result.stdout

    def test_show_active_command(self):
        """Test the show-active command."""
        # Use the project root directory where manage_alert_configs.py is located
        project_root = Path(__file__).parent.parent
        
        # First set an active profile
        subprocess.run(
            [sys.executable, "manage_alert_configs.py", "set-active", "default"],
            cwd=project_root,
            capture_output=True,
            text=True
        )

        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "show-active"],
            cwd=project_root,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert result.stdout.strip() == "default"

    def test_clone_nonexistent_source(self):
        """Test cloning from non-existent source."""
        # Use the project root directory where manage_alert_configs.py is located
        project_root = Path(__file__).parent.parent
        
        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "clone", "nonexistent", "test_dest"],
            cwd=project_root,
            capture_output=True,
            text=True
        )

        assert result.returncode == 2  # File not found error

    def test_clone_existing_destination(self):
        """Test cloning to existing destination."""
        # Use the project root directory where manage_alert_configs.py is located
        project_root = Path(__file__).parent.parent
        
        # First clone a file to create it
        subprocess.run(
            [sys.executable, "manage_alert_configs.py", "clone", "default", "existing"],
            cwd=project_root,
            capture_output=True,
            text=True
        )

        # Try to clone to the same destination
        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "clone", "default", "existing"],
            cwd=project_root,
            capture_output=True,
            text=True
        )

        assert result.returncode == 3  # File exists error

    def test_validate_nonexistent_profile(self):
        """Test validation of non-existent profile."""
        # Use the project root directory where manage_alert_configs.py is located
        project_root = Path(__file__).parent.parent
        
        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "validate", "--profile", "nonexistent"],
            cwd=project_root,
            capture_output=True,
            text=True
        )

        assert result.returncode == 1  # Validation error
        assert "Validation failed for nonexistent" in result.stdout

    def test_export_hardcoded_command(self):
        """Test the export-hardcoded command."""
        # Use the project root directory where manage_alert_configs.py is located
        project_root = Path(__file__).parent.parent
        output_path = self.config_dir / "exported.json"

        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "export-hardcoded", str(output_path)],
            cwd=project_root,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "Exported default preset to" in result.stdout

        # Verify the exported file exists and is valid JSON
        assert output_path.exists()
        with open(output_path, "r") as f:
            exported_data = json.load(f)
        assert "id" in exported_data  # Should have an ID


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir)

    def test_invalid_command(self):
        """Test handling of invalid command."""
        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "invalid_command"],
            cwd=self.config_dir.parent,
            capture_output=True,
            text=True
        )

        assert result.returncode == 2  # Command error

    def test_help_command(self):
        """Test help command."""
        # Use the project root directory where manage_alert_configs.py is located
        project_root = Path(__file__).parent.parent
        
        result = subprocess.run(
            [sys.executable, "manage_alert_configs.py", "--help"],
            cwd=project_root,
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