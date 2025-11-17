import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import jsonschema

from concern_level import ConcernLevel

LOGGER = logging.getLogger(__name__)
SAFE_GLOBALS = {"abs": abs, "max": max, "min": min, "round": round}


class SessionAlertOverrides:
    def __init__(self) -> None:
        self.overrides: Dict[str, Dict[str, Any]] = {}

    def set_override(self, condition_id: str, patch: Dict[str, Any]) -> None:
        existing = self.overrides.get(condition_id, {})
        existing.update(patch)
        self.overrides[condition_id] = existing

    def remove_override(self, condition_id: str) -> None:
        self.overrides.pop(condition_id, None)

    def clear(self) -> None:
        self.overrides.clear()

    def apply(self, conditions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        patched: List[Dict[str, Any]] = []
        for cond in conditions:
            override = self.overrides.get(cond.get("id", ""))
            if override:
                merged = dict(cond)
                merged.update(override)
                patched.append(merged)
            else:
                patched.append(dict(cond))
        return patched


class AlertConfigManager:
    def __init__(
        self,
        config_dir: str = "alert_configs",
        default_profile: str = "default",
    ):
        self.config_dir = Path(config_dir)
        self.default_profile = default_profile
        self.schema_path = self.config_dir / "schemas" / "alert_config.schema.json"
        self.local_user_dir = self.config_dir / "user"
        self.global_user_dir = (
            Path.home() / ".config" / "trading-stats-tracker" / "alert_configs"
        )
        self.active_profile_file = self.config_dir / "active_config.json"
        self.env = os.environ.get("CONFIG_ENV")
        self.session_overrides = SessionAlertOverrides()
        self.current_profile_name: Optional[str] = None
        self.current_config: Optional[Dict[str, Any]] = None
        self.config_cache: Dict[str, Dict[str, Any]] = {}
        self.schema = self._load_schema()
        self.active_profile_override = self._read_active_profile()

    def _load_schema(self) -> Dict[str, Any]:
        try:
            with open(self.schema_path, "r", encoding="utf-8") as schema_file:
                return json.load(schema_file)
        except FileNotFoundError:
            LOGGER.warning("Alert config schema not found at %s", self.schema_path)
            return {}

    def _read_active_profile(self) -> Optional[str]:
        if not self.active_profile_file.exists():
            return None
        try:
            with open(self.active_profile_file, "r", encoding="utf-8") as active_file:
                payload = json.load(active_file)
            return payload.get("name")
        except Exception as exc:
            LOGGER.warning("Failed to read active profile override: %s", exc)
            return None

    def _validate(self, payload: Dict[str, Any]) -> bool:
        if not self.schema:
            return True
        try:
            jsonschema.validate(instance=payload, schema=self.schema)
            return True
        except jsonschema.ValidationError as exc:
            LOGGER.warning("Alert config validation failed: %s", exc)
            return False

    def _format_value(self, value: Any) -> str:
        if isinstance(value, str):
            return json.dumps(value)
        return str(value)

    def _normalize_condition(self, condition: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(condition)
        when_expr = normalized.get("when", "").strip()
        if not when_expr:
            primary_field = normalized.get("primary_field")
            operator = normalized.get("operator")
            comparison_field = normalized.get("comparison_field")
            threshold = normalized.get("threshold")
            if not primary_field or not operator:
                raise ValueError(
                    f"Condition {normalized.get('id')} requires 'when' or structured fields"
                )

            left = (
                f"abs({primary_field})"
                if normalized.get("abs_value")
                else primary_field
            )
            right = (
                comparison_field if comparison_field else self._format_value(threshold)
            )
            expressions = [f"{left} {operator} {right}"]

            additional = normalized.get("additional_conditions", [])
            for extra in additional:
                exc_field = extra.get("field")
                exc_operator = extra.get("operator")
                exc_value = extra.get("value")
                if not (exc_field and exc_operator and exc_value is not None):
                    continue
                expressions.append(
                    f"{exc_field} {exc_operator} {self._format_value(exc_value)}"
                )

            when_expr = " and ".join(expressions)

        normalized["when"] = when_expr
        normalized.setdefault("enabled", True)
        normalized.setdefault("throttle_secs", 0)
        return normalized

    def _find_profile_path(self, profile_name: str) -> Optional[Path]:
        candidate = Path(profile_name)
        if candidate.is_absolute() and candidate.exists():
            return candidate

        if candidate.parent != Path() and candidate.exists():
            return candidate

        if candidate.suffix == "":
            name = f"{candidate}.json"
        else:
            name = candidate.name

        search_dirs = [
            self.local_user_dir,
            self.global_user_dir,
        ]

        if self.env:
            search_dirs.append(self.config_dir / "presets" / self.env)

        search_dirs.append(self.config_dir / "presets")

        for parent in search_dirs:
            candidate_path = parent / name
            if candidate_path.exists():
                return candidate_path

        return None

    def load_config(self, profile_name: Optional[str] = None) -> Dict[str, Any]:
        env_override = os.environ.get("ALERT_CONFIG_NAME")
        resolved_name = (
            profile_name
            or env_override
            or self._read_active_profile()
            or self.default_profile
        )
        if resolved_name in self.config_cache:
            config = self.config_cache[resolved_name]
        else:
            path = self._find_profile_path(resolved_name)
            if not path:
                raise FileNotFoundError(f"Alert profile '{resolved_name}' not found")
            with open(path, "r", encoding="utf-8") as config_file:
                config = json.load(config_file)
            if not self._validate(config):
                raise ValueError(
                    f"Alert profile '{resolved_name}' failed schema validation"
                )
            config["conditions"] = [
                self._normalize_condition(cond) for cond in config.get("conditions", [])
            ]
            self.config_cache[resolved_name] = config

        self.current_profile_name = resolved_name
        self.current_config = dict(config)
        return self.get_active_config()

    def get_active_config(self) -> Dict[str, Any]:
        if not self.current_config:
            return self.load_config()
        config_copy = dict(self.current_config)
        config_copy["conditions"] = self.session_overrides.apply(
            self.current_config.get("conditions", [])
        )
        return config_copy

    def list_profiles(self) -> List[Dict[str, str]]:
        results: List[Dict[str, str]] = []
        seen: set[str] = set()

        directories = [
            ("local_user", self.local_user_dir),
            ("global_user", self.global_user_dir),
        ]
        if self.env:
            directories.append(("env_presets", self.config_dir / "presets" / self.env))
        directories.append(("repo_presets", self.config_dir / "presets"))

        for entry in directories:
            if entry is None:
                continue
            source, directory = entry
            if not directory.exists():
                continue
            for candidate in directory.glob("*.json"):
                name = candidate.stem
                if name in seen:
                    continue
                seen.add(name)
                results.append(
                    {
                        "name": name,
                        "source": source,
                        "path": str(candidate.resolve()),
                    }
                )
        return results

    def get_profile_path(self, profile_name: str) -> Optional[Path]:
        return self._find_profile_path(profile_name)

    def set_active_profile(self, profile_name: str) -> None:
        if not self._find_profile_path(profile_name):
            raise FileNotFoundError(f"Alert profile '{profile_name}' not found")
        self.active_profile_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.active_profile_file, "w", encoding="utf-8") as handle:
            json.dump({"name": profile_name}, handle)
        self.active_profile_override = profile_name

    def clear_active_profile(self) -> None:
        if self.active_profile_file.exists():
            self.active_profile_file.unlink()
        self.active_profile_override = None

    def get_active_profile_name(self) -> str:
        env_override = os.environ.get("ALERT_CONFIG_NAME")
        active_override = self._read_active_profile()
        return (
            self.current_profile_name
            or env_override
            or active_override
            or self.default_profile
        )

    def create_config_copy(self, source_name: str, target_name: str) -> Path:
        source_path = self._find_profile_path(source_name)
        if not source_path:
            raise FileNotFoundError(f"Source profile '{source_name}' not found")

        target_path = self.local_user_dir / f"{target_name}.json"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            raise FileExistsError(f"Target profile '{target_name}' already exists")

        shutil.copy(source_path, target_path)
        return target_path

    def save_config(self, config_data: Dict[str, Any], profile_name: str) -> Path:
        target = self.local_user_dir / f"{profile_name}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as output:
            json.dump(config_data, output, indent=2)

        backup_name = (
            f"{profile_name}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
        )
        backup_path = self.config_dir / "backups" / backup_name
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(target, backup_path)
        return target


class ConditionEvaluator:
    def __init__(self, config: Dict[str, Any]):
        self.conditions = config.get("conditions", [])
        self.color_rules = config.get("color_rules", [])

    def _eval_expr(self, expression: str, context: Dict[str, Any]) -> bool:
        try:
            return bool(eval(expression, SAFE_GLOBALS, context))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to evaluate expression '%s': %s", expression, exc)
            return False

    def _normalize_level(self, level_value: str) -> ConcernLevel:
        if not isinstance(level_value, str):
            return ConcernLevel.DEFAULT
        try:
            return ConcernLevel[level_value.upper()]
        except KeyError:
            LOGGER.warning("Unknown concern level '%s'; defaulting", level_value)
            return ConcernLevel.DEFAULT

    def evaluate(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        seen_groups: set[str] = set()
        for condition in self.conditions:
            if not condition.get("enabled", True):
                continue
            group = condition.get("group", "")
            if group in seen_groups:
                continue
            expression = condition.get("when", "")
            if not expression:
                continue
            if self._eval_expr(expression, context):
                seen_groups.add(group)
                level = self._normalize_level(condition.get("level", "DEFAULT"))
                results.append(
                    {
                        "id": condition.get("id"),
                        "group": group,
                        "message": condition.get("message", ""),
                        "extra_message": condition.get("extra_message", ""),
                        "level": level,
                        "throttle_secs": condition.get("throttle_secs", 0),
                    }
                )
        return results
