# Implementation Tasks for JSON Alert Config

## 1. Repository Scaffolding
- [ ] Create `alert_configs/` tree with subfolders: `presets/`, `user/` (gitignored), `backups/` (gitignored), `schemas/`.
- [ ] Add default preset JSON (mirrors current hard-coded thresholds) and placeholder aggressive preset.
- [ ] Write `.gitignore` entries for `alert_configs/user/`, `alert_configs/backups/`, and user config path under `~/.config/trading-stats-tracker/`.
- [ ] Draft `alert_config.schema.json` (JSON Schema) under `alert_configs/schemas/`.

## 2. AlertConfigManager
- [ ] Implement `AlertConfigManager` (likely in new module `alert_config_manager.py`) that:
  - Discovers configs in source precedence (user dirs → env presets → repo presets).
  - Resolves profile name from CLI arg/env var/default.
  - Loads & caches JSON, validates with schema, and normalizes structured fields (`threshold`, `operator`, etc.) into `when`.
  - Exposes `load_config`, `get_active_config`, `list_profiles`, `create_config_copy`, `save_config`, and backup handling.
- [ ] Add integration tests/unit tests for manager behaviors (discovery order, schema validation, normalization).

## 3. ConditionEvaluator
- [ ] Create `ConditionEvaluator` that:
  - Accepts the active config (`conditions`, `color_rules`, `context_fields`).
  - Evaluates each condition’s `when` expression safely via `ast` over the metrics context.
  - Short-circuits within a `group` (first match wins) and returns tuples for alert construction.
  - Applies `enabled` flag, `throttle_secs`, and handles message formatting.
- [ ] Add tests covering expression evaluation, group prioritization, disabled rules, and color rules.

## 4. SessionAlertOverrides (Runtime/UI Only)
- [ ] Implement `SessionAlertOverrides` to manage purely in-memory overrides injected by the running UI (no persistence to disk or CLI hooks).
- [ ] Provide APIs to set/remove overrides and clear them when the UI resets; ensure they expire when the process exits.
- [ ] Update `AlertConfigManager` to merge runtime overrides into the active config before evaluation.

## 5. TradeStatsProcessor Integration
- [ ] Replace hard-coded condition blocks in `trade_stats_processor.py` with calls to the new manager/evaluator.
- [ ] Ensure computed metrics supply every field listed under `context_fields.required`; add guards/logging if data is missing.
- [ ] Update alert creation flow to consume evaluator output (`message`, `level`, `extra_message`, `color_rules`).
- [ ] Maintain fallback path: if JSON fails to load, use existing hard-coded conditions (log warning).

## 6. Tooling & CLI Support
- [ ] Add `manage_alert_configs.py` (or similar) with commands: `clone`, `list`, `validate`, `export-hardcoded`, `set-active`.
- [ ] Introduce `make validate_alerts` target that runs schema validation on all preset/user configs.
- [ ] Update `README.md` with instructions for switching profiles, cloning configs, the UI-only override behavior, and running the validation target.

## 7. Migration & Backups
- [ ] Implement export script/function to dump current hard-coded conditions into JSON (bootstrap default preset).
- [ ] Ensure `AlertConfigManager.save_config` writes timestamped copies into `alert_configs/backups/`.
- [ ] Document rollback steps (how to restore from backups or re-enable hard-coded mode).

## 8. Future UI Hooks (Preparatory Work)
- [ ] Expose Python APIs for listing profiles, selecting active profile, enumerating conditions by group, and applying per-condition overrides.
- [ ] Add placeholder wiring in `app.py` (e.g., stub methods or TODOs) indicating how future PyQt components will trigger profile switches or edits.
