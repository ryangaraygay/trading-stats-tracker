# JSON Alert Configuration Design

This document defines a standalone JSON-based alert configuration system for trading statistics and alerts, including storage layout, schema, evaluation flow, session overrides, and migration from the current hard-coded rules.

## Background
- Alert conditions are currently hard-coded inside `trade_stats_processor.py` (around line 309) as Python dicts containing lambda predicates, `ConcernLevel`, and message payloads. Any change requires a code edit and redeploy.
- The goals are:
  1. Store alert conditions in JSON files editable without Python changes.
  2. Support copying/modifying alert profiles (e.g., default, conservative, aggressive).
  3. Prepare for a future UI for managing configurations.
  4. Support session-level overrides that apply only for the current run.

## Configuration Storage Layout
```text
trading-stats-tracker/
└── alert_configs/
    ├── schemas/
    │   └── alert_config.schema.json          # JSON Schema for validation
    ├── presets/                              # versioned, shipped configs
    │   ├── default.json
    │   └── demo-aggressive.json
    ├── user/                                 # gitignored, user-owned
    │   └── ryan-day-trading.json
    └── backups/                              # optional automatic snapshots
        ├── default_2024-01-15.json
        └── conservative_2024-01-15.json
```
- `AlertConfigManager` reads configs from an ordered list of sources (highest wins), then applies in-memory UI overrides on top:
  1. User configs (`~/.config/trading-stats-tracker/alert_configs` and `alert_configs/user/`).
  2. Environment-specific presets (`alert_configs/presets/<CONFIG_ENV>/`).
  3. Repository presets (`alert_configs/presets`).
- Runtime overrides are injected directly by the UI (no files, no CLI flags) and live only in memory until the app quits.
- Active profile selection:
  - CLI flag `--alert-config <name_or_path>` (future) or GUI dropdown.
  - Env var `ALERT_CONFIG_NAME` (maps to `<dir>/<name>.json`).
  - Falls back to `default` if unspecified.

## Condition Model & JSON Schema

At the core, each alert rule is evaluated from a boolean expression string `when` using a sandboxed `ast` evaluator. All other structured fields are either metadata or syntactic sugar compiled into a `when` expression by the loader.

### High-Level Schema
```json
{
  "schema_version": "1.0",
  "id": "default",
  "name": "Default Risk Controls",
  "description": "Baseline guardrails for ES scalping",
  "metadata": {
    "created_by": "ryan",
    "created_at": "2024-06-01T00:00:00Z",
    "source": "repo"             // repo | user | session
  },
  "context_fields": {            // metrics expected from TradeStatsProcessor
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
      "id": "trade-count-max",
      "group": "trade_count",
      "label": "Trade Count Limit",
      "when": "completed_trades >= 30",
      "level": "CRITICAL",
      "message": "Stop. Maximum trades for the day reached.",
      "extra_message": "{completed_trades}",
      "throttle_secs": 0,
      "enabled": true
    },
    {
      "id": "trade-count-goal-positive",
      "group": "trade_count",
      "label": "Trade Count Goal (Profitable)",
      "when": "completed_trades >= 20 and total_profit_or_loss > 0",
      "level": "OK",
      "message": "Wind down. You've reached your trade count goal.",
      "extra_message": "{completed_trades}",
      "enabled": true
    },
    {
      "id": "pnl-down-critical",
      "group": "profit_loss",
      "label": "P&L Drawdown Critical",
      "when": "total_profit_or_loss < -2100",
      "level": "CRITICAL",
      "message": "Stop. Protect your capital.",
      "extra_message": "{total_profit_or_loss:+,}",
      "enabled": true
    },
    {
      "id": "winrate-low-warning",
      "group": "win_rate",
      "label": "Low Win Rate",
      "when": "win_rate <= 25 and profit_factor < 1.0 and completed_trades >= 10",
      "level": "WARNING",
      "message": "Reset. Win Rate very low.",
      "extra_message": "{directional_bias_extramsg}",
      "enabled": true
    },
    {
      "id": "profit-factor-low",
      "group": "profit_factor",
      "label": "Low Profit Factor",
      "when": "profit_factor < 1.5 and completed_trades >= 5",
      "level": "CAUTION",
      "message": "Slow down. Profit Factor low.",
      "extra_message": "{directional_bias_extramsg}",
      "enabled": true
    },
    {
      "id": "losing-streak-critical",
      "group": "losing_streak",
      "label": "Deep Losing Streak",
      "when": "streak_tracker.streak <= -7",
      "level": "CRITICAL",
      "message": "Stop Now. Protect the version of YOU that will trade well tomorrow.",
      "enabled": true
    },
    {
      "id": "loss-max-size-warning",
      "group": "loss_max_size",
      "label": "Max Loss Size Warning",
      "when": "loss_max_size >= 10",
      "level": "WARNING",
      "message": "Reset. Size down.",
      "enabled": true
    },
    {
      "id": "drawdown-critical",
      "group": "drawdown",
      "label": "Max Drawdown",
      "when": "current_drawdown < -3000",
      "level": "CRITICAL",
      "message": "Stop Now. Maximum drawdown.",
      "extra_message": "{current_drawdown:+,}",
      "enabled": true
    },
    {
      "id": "open-position-size-caution",
      "group": "simple_conditions",
      "label": "Large Open Position",
      "when": "abs(open_position_size) >= 3",
      "level": "CAUTION",
      "message": "",
      "enabled": true
    },
    {
      "id": "avg-duration-warning",
      "group": "simple_conditions",
      "label": "Short Winning Trade Duration",
      "when": "win_avg_secs_vs_loss_avg_secs < 60",
      "level": "WARNING",
      "message": "",
      "enabled": true
    }
  ],
  "color_rules": [
    {
      "metric": "win_rate",
      "rules": [
        { "when": "win_rate <= 25", "color": "#b00020" },
        { "when": "win_rate <= 40", "color": "#f9a825" }
      ]
    }
  ]
}
```

### Optional Structured Fields (from Obsidian Draft)

For UI editing, conditions may optionally include a more structured representation that the loader compiles into the `when` string:
- `primary_field`: The main metric being thresholded (e.g., `completed_trades`, `total_profit_or_loss`).
- `threshold` and `operator`: Simple comparison (`>=`, `<=`, `<`, `>`, `==`).
- `additional_conditions`: A list of `{field, operator, value}` that are combined with `AND`.
- `abs_value`: When true, the comparison is applied to `abs(primary_field)`.
- `comparison_field`: Name of another metric used in place of a literal `value`.

Example (UI-friendly form):
```json
{
  "id": "winrate-low-warning",
  "group": "win_rate",
  "primary_field": "win_rate",
  "threshold": 25,
  "operator": "<=",
  "additional_conditions": [
    { "field": "profit_factor", "operator": "<", "value": 1.0 },
    { "field": "completed_trades", "operator": ">=", "value": 10 }
  ],
  "level": "WARNING",
  "message": "Reset. Win Rate very low.",
  "extra_message": "{directional_bias_extramsg}",
  "enabled": true
}
```

`AlertConfigManager` may support this structure but must always normalize to a `when` expression (e.g., `win_rate <= 25 and profit_factor < 1.0 and completed_trades >= 10`) before evaluation. The evaluation engine only understands `when`.

## Condition Categories (Coverage from Current System)

Grounded in the existing `trade_stats_processor.py` logic, the configuration should cover at least these groups:
- `trade_count`: Overtrading / trade count goals.
- `profit_loss`: Net P&L drawdowns and profit targets.
- `win_rate`: Overall win-rate quality.
- `profit_factor`: Reward-to-risk quality.
- `losing_streak`: Consecutive loss streaks.
- `loss_max_size`: Max single-trade loss.
- `loss_scaled_count`: Number of scaled-into losers.
- `drawdown`: Realized drawdown from peak.
- `simple_conditions`: Non-message-based color cues (e.g., open position size, duration ratios).

Each of these should be represented in JSON with one or more `conditions` entries, typically mirroring the existing thresholds and levels from the hard-coded lists.

## Loading, Merge & Evaluation Process
1. `AlertConfigManager.load_active_config()`:
   - Resolve the active profile name using CLI flag/env var/default.
   - Locate JSON from sources in precedence order (user → env presets → repo presets).
   - Load and validate JSON against `alert_config.schema.json`.
   - Normalize any structured condition fields into `when` expressions.
2. Cache the parsed config and expose it to `TradeStatsProcessor`.
3. `TradeStatsProcessor` computes the metrics per account and builds a context dict containing all `context_fields.required`.
4. `ConditionEvaluator`:
   - Iterates over `conditions` (ordered as stored).
   - For each `group`, optionally short-circuits on the first matching rule (to mimic current “first-hit wins” semantics).
   - Evaluates `when` safely via a sandboxed `ast` interpreter.
   - Constructs `AlertMessage` instances from matches by mapping `level` strings to `ConcernLevel`, applying `message`/`extra_message` formatting, and honoring `throttle_secs`.
5. Apply session overrides just before evaluation:
   - Merge override entries keyed by `condition.id` into the base condition set (e.g., update `when`, `level`, `message`, or `enabled`).

## Copy / Modify Workflow
- Copying a config is simple file duplication:
  - Example: `alert_configs/presets/default.json` → `alert_configs/user/focus_mode.json`.
- A small CLI helper (future):  
  `python manage_alert_configs.py clone default focus_mode`
  1. Validates the source JSON against the schema.
  2. Writes the new config into `alert_configs/user/`.
  3. Optionally switches the active profile by updating `alert_configs/active_config.json` or setting `ALERT_CONFIG_NAME`.
- Backups:
  - `AlertConfigManager` may maintain timestamped copies in `alert_configs/backups/` on save.
  - Backups are never auto-loaded but can be restored manually or via a CLI `restore` command.

## Session-Level Overrides

### Data Model
- `SessionAlertOverrides` maintains an in-memory dict keyed by `condition.id`:
```json
{
  "trade-count-max": {
    "when": "completed_trades >= 25",
    "level": "WARNING"
  },
  "pnl-down-critical": {
    "enabled": false
  }
}
```

### Sources & Lifetime
- Overrides are injected only by the running UI (e.g., sliders, numeric inputs, dropdowns) and never persisted to disk or exposed via CLI.
- The override dict lives strictly in memory while the UI session is active; once the app restarts or the user clears overrides, the base JSON profile applies again.
- Precedence:
  - Runtime overrides are applied on top of the active JSON config immediately before evaluation.
  - Because there is no persistence, saving an override requires the user to explicitly edit/clone a JSON profile via the forthcoming UI tools.

### Example Usage (Conceptual)
- During a session (UI actions only):
  - Lower trade limit: UI control updates override for `"trade-count-max"` with a more conservative `when`.
  - Tighten P&L limit: UI control overrides `"pnl-down-critical"` threshold in the expression.
  - Disable a rule: UI toggle sets `"enabled": false` for a given `id`.

## Core Components & APIs

### AlertConfigManager
Responsible for locating, loading, validating, normalizing, and caching alert configuration JSON.

Key responsibilities:
- Discover configs from `alert_configs/` tree and user/config dirs.
- Validate against JSON Schema.
- Normalize structured condition fields into `when`.
- Apply session overrides.
- Provide a stable API for the rest of the app.

Sketch:
```python
class AlertConfigManager:
    def __init__(self, config_dir: str = "alert_configs"):
        self.config_dir = config_dir
        self.current_profile_name: str | None = None
        self.current_config: dict | None = None
        self.session_overrides = SessionAlertOverrides()
        self.config_cache: dict[str, dict] = {}

    def load_config(self, profile_name: str = "default") -> dict:
        """Locate, read, validate, and cache a configuration profile."""

    def save_config(self, config_data: dict, profile_name: str) -> None:
        """Persist configuration JSON, optionally writing a backup snapshot."""

    def create_config_copy(self, source_name: str, new_name: str) -> None:
        """Clone an existing profile into a new one under user or presets."""

    def get_active_config(self) -> dict:
        """Return the currently loaded config with overrides applied."""

    def list_profiles(self) -> list[str]:
        """List discoverable profile names across presets/user dirs."""
```

### ConditionEvaluator
Encapsulates evaluation of normalized `conditions` against a metrics context.

Sketch:
```python
class ConditionEvaluator:
    def __init__(self, config: dict):
        self.config = config

    def evaluate(self, context: dict) -> list[tuple[str, str, str]]:
        """Return a list of (message, level, extra_message) for matching rules."""
```

### SessionAlertOverrides
Simple in-memory overlay for condition tweaks that last only during a session.

Sketch:
```python
class SessionAlertOverrides:
    def __init__(self):
        self.overrides: dict[str, dict] = {}

    def set_override(self, condition_id: str, patch: dict) -> None:
        """Update fields (when, level, message, enabled, etc.) for a condition."""

    def get_override(self, condition_id: str) -> dict | None:
        """Fetch override for a condition, if any."""

    def clear(self) -> None:
        """Remove all overrides."""
```

## Backward Compatibility & Migration
- Fallback behavior:
  - If JSON config fails to load or validate, the system MUST fall back to the current hard-coded conditions in `trade_stats_processor.py`.
  - A clear warning should be logged to stderr or a log file indicating that fallback mode is active.
- Migration tool (optional but recommended):
  - Add a small script (e.g., `python manage_alert_configs.py export-hardcoded default`) that:
    1. Reads the current hard-coded conditions.
    2. Emits a JSON file under `alert_configs/presets/default.json` matching the new schema.
    3. Acts as a one-time bootstrap for the initial JSON config.
- Gradual rollout:
  - During migration, keep both hard-coded and JSON paths available behind a feature flag or config switch.
  - Once stable, switch the default path to JSON and keep the hard-coded path as a safety net only.

## Implementation Steps (Consolidated)
1. **Foundations**
   - Add `alert_configs/` structure (presets/user/backups/schemas).
   - Define and check in `alert_config.schema.json`.
2. **Config Manager**
   - Implement `AlertConfigManager` to handle discovery, validation, normalization, caching, and backups.
3. **Evaluation Engine**
   - Implement `ConditionEvaluator` using the `when`/AST approach and integrate into `TradeStatsProcessor` in place of the embedded condition lists.
4. **Session Overrides**
   - Implement `SessionAlertOverrides` and wire it into the manager’s merge pipeline.
5. **Backward Compatibility**
   - Add fallback logic to use hard-coded conditions when JSON is missing/invalid.
   - (Optional) Build migration/export tooling.
6. **Developer Tooling**
   - Add `make validate_alerts` target to run schema validation on configs.
   - Document workflows in `README.md`.
7. **UI & CLI Hooks (Future)**
   - Expose APIs for listing/loading/saving profiles and applying session overrides.
   - Add placeholder hooks in `app.py` for switching profiles at runtime (e.g., via a dropdown).

This design specifies an expression-based architecture with clear configuration storage, evaluation, overrides, and migration paths, along with detailed condition coverage, structured condition hints, backup/file management options, and an explicit backward-compatibility story.
