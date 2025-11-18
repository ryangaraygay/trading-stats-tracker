# Bug Report – JSON Alert Configuration

Tracking only confirmed defects on branch `specs/001-json-alert-config/design.md`.

## Summary
- **Total Open Bugs:** 3 (all Medium severity)
- All previously reported Critical items were false positives (see `techdebt.md`).

---

### BUG‑001 – Active Profile File Is Tracked In Git
**Severity:** Medium  
**Location:** `alert_config_manager.py:146-215`  
**Status:** Open

`set_active_profile()` writes `alert_configs/active_config.json` inside the repository and the file is not ignored. Running `manage_alert_configs.py set-active …` leaves the working tree dirty and risks committing local profile choices.

**Impact:** Developers can accidentally commit personal config state, causing noise in diffs and leaking defaults.  
**Fix:** Store the active-profile marker under `~/.config/trading-stats-tracker` (preferred) or add the file to `.gitignore`.

---

### BUG‑002 – Win/Loss Duration Comparison Lost
**Severity:** Medium  
**Location:** `trade_stats_processor.py:700-748`, `alert_configs/presets/default.json:150-170`  
**Status:** Open

The context exposes only `win_avg_secs_vs_loss_avg_secs`, populated with `win_avg_secs.total_seconds()`. The default preset relies on this value to represent “wins vs losses” duration, so the legacy “wins taking longer than losses” rule can no longer be expressed.

**Impact:** The "Short Winning Trade Duration" alert fires on an absolute threshold instead of comparing win/loss averages, leading to false positives/negatives.  
**Fix:** Publish both `win_avg_secs` and `loss_avg_secs` (or their ratio) to the JSON context and update presets accordingly.

---

### BUG‑003 – `validate` Command Changes Active Profile
**Severity:** Medium  
**Location:** `manage_alert_configs.py:66-96`  
**Status:** Open

`manage_alert_configs.py validate` calls `load_config()` for every profile, which updates `current_profile_name`. After validation, whatever profile happened to be processed last becomes active without user intent.

**Impact:** Running the validate command silently switches the alerts profile, causing unexpected behavior in the UI/Hammerspoon.  
**Fix:** Perform schema validation without mutating `AlertConfigManager` state (e.g., load JSON via `Path.read_text()` or use a fresh manager per profile).

---

## Testing Notes
- Re-run `manage_alert_configs.py validate` after fixing BUG‑003 to ensure the active profile remains unchanged.
- Add regression tests covering the win/loss duration context once BUG‑002 is fixed.

---

All other previously reported issues were reclassified as design decisions or low-priority tech debt; see `techdebt.md` for those entries.
