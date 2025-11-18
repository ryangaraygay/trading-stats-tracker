# Bug Report: JSON Alert Configuration Implementation

This document lists bugs and issues found during code review of the JSON Alert Configuration feature branch (`specs/001-json-alert-config/design.md`).

## Summary

The JSON Alert Configuration implementation adds a configurable alert system but contains several critical bugs that could cause runtime failures, security vulnerabilities, and silent alert loss.

**Total Issues Found**: 15 issues (4 Critical, 11 Medium/Low priority)

*Note: Additional type checking errors were discovered during analysis and are documented below.*

---

## Critical Issues

### 1. AttributeError in Alert Config Manager Initialization
**Location**: `trade_stats_processor.py:35-42`  
**Severity**: Critical  
**Status**: Unfixed

```python
def _initialize_alert_config_manager(self):
    try:
        manager = AlertConfigManager()
        manager.load_config()
        return manager
    except Exception as exc:
        LOGGER.warning("Alert config manager unavailable: %s", exc)
        return None  # BUG: Returns None, will cause AttributeError later
```

**Problem**: When the alert config manager fails to initialize, it returns `None`. Later code like `self._evaluate_alerts()` calls `self.alert_config_manager.method()` which will crash with:
```
AttributeError: 'NoneType' object has no attribute
```

**Impact**: Complete application crash when alert config initialization fails  
**Fix**: Return a fallback/mock manager or add None checks throughout the codebase

---

### 2. Security Vulnerability via eval()
**Location**: `alert_config_manager.py:306-311`  
**Severity**: Critical  
**Status**: Unfixed

```python
def _eval_expr(self, expression: str, context: Dict[str, Any]) -> bool:
    try:
        return bool(eval(expression, SAFE_GLOBALS, context))  # SECURITY BUG
    except Exception as exc:
        LOGGER.warning("Failed to evaluate expression '%s': %s", expression, exc)
        return False
```

**Problem**: Using `eval()` with user-controlled expressions is dangerous. The `context` dict contains actual data values that could be manipulated to execute arbitrary code.

**Impact**: Potential remote code execution if malicious expressions are injected  
**Fix**: Replace with safe expression evaluator (ast.literal_eval or custom parser)

---

### 3. Silent Alert Loss
**Location**: `trade_stats_processor.py:827-830`  
**Severity**: Critical  
**Status**: Unfixed

```python
def _build_alert_messages(self, account_name: str, matches) -> list:
    alerts = []
    for match in matches:
        message = match.get("message", "")
        level = match.get("level", ConcernLevel.DEFAULT)
        extra = match.get("extra_message", "")
        if not message:
            continue  # BUG: Silently drops alerts without logging
```

**Problem**: Alerts without messages are silently discarded, which could hide important alerts that should display even with empty messages.

**Impact**: Important trading alerts may be lost silently  
**Fix**: Log warnings when alerts are dropped or handle empty messages differently

---

### 4. Missing Error Handling in Aggregated Account Processing
**Location**: `trade_stats_processor.py:760-766`  
**Severity**: Critical  
**Status**: Unfixed

```python
self.account_trading_alerts[CONST.ALL_ACCOUNTS] = (
    self._build_alert_messages(
        CONST.ALL_ACCOUNTS, self._evaluate_alerts(alert_context)  # BUG: No error handling
    )
)
```

**Problem**: If `_evaluate_alerts()` fails for the aggregated account, it could crash the entire stats computation.

**Impact**: Application crash when processing aggregated accounts  
**Fix**: Add try-catch around the aggregated alert generation

---

## Medium Priority Issues

### 5. Group-Based Filtering May Suppress Valid Alerts
**Location**: `alert_config_manager.py:324-336`  
**Severity**: Medium  
**Status**: Unfixed

```python
def evaluate(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen_groups: set[str] = set()
    for condition in self.conditions:
        # ... evaluation logic ...
        if self._eval_expr(expression, context):
            seen_groups.add(group)  # BUG: Only first condition in each group triggers
            # Add to results...
```

**Problem**: Only the first matching condition per group triggers. This may be intentional but could suppress multiple valid alerts in the same group.

**Impact**: Multiple valid alerts may be suppressed  
**Fix**: Clarify if this is intended behavior or if all matching conditions should trigger

---

### 6. Configuration Path Resolution Edge Cases
**Location**: `alert_config_manager.py:147-175`  
**Severity**: Medium  
**Status**: Unfixed

**Problem**: The profile path resolution logic has several edge cases that could fail silently or return wrong paths, particularly around:
- Relative vs absolute path handling
- Environment variable interactions
- Missing directory creation

**Impact**: Configuration loading failures that are hard to debug  
**Fix**: Add comprehensive path validation and clearer error messages

---

### 7. Missing Schema Validation Fallback
**Location**: `alert_config_manager.py:72-99`  
**Severity**: Medium  
**Status**: Unfixed

```python
def _load_schema(self) -> Dict[str, Any]:
    try:
        with open(self.schema_path, "r", encoding="utf-8") as schema_file:
            return json.load(schema_file)
    except FileNotFoundError:
        LOGGER.warning("Alert config schema not found at %s", self.schema_path)
        return {}  # BUG: Returns empty dict, skips validation
```

**Problem**: When the JSON schema file is missing, validation is skipped without proper fallback to hardcoded conditions.

**Impact**: Invalid configurations may be loaded without validation  
**Fix**: Implement proper fallback to hardcoded conditions when schema is unavailable

---

### 8. Cache Invalidation Missing
**Location**: `alert_config_manager.py:185-200`  
**Severity**: Medium  
**Status**: Unfixed

**Problem**: Config caching doesn't handle cache invalidation when:
- Files change on disk
- Overrides are applied
- Active profile is switched

**Impact**: Stale configuration data may be used  
**Fix**: Implement proper cache invalidation strategies

---

### 9. Poor Variable Naming
**Location**: `alert_config_manager.py:134`  
**Severity**: Medium  
**Status**: Unfixed

```python
for extra in additional:
    exc_field = extra.get("field")  # BUG: Should be "extra_field"
    exc_operator = extra.get("operator")
    exc_value = extra.get("value")
```

**Problem**: Variable named `exc_field` instead of `extra_field` reduces code clarity and could cause confusion.

**Impact**: Code maintainability issues  
**Fix**: Rename variable to `extra_field` for clarity

---

### 9. Active Profile File Commits Local State
**Location**: `alert_config_manager.py:146-215`, repository root  
**Severity**: Medium  
**Status**: Unfixed

**Problem**: `set_active_profile()` writes `alert_configs/active_config.json` inside the repo and the file is not ignored. Running `manage_alert_configs.py set-active …` (or any future UI hook) leaves the working tree dirty and risks committing machine-specific state.

**Impact**: Developers can accidentally commit local profile selections, causing confusing diffs and leaking personal defaults.  
**Fix**: Store the active profile marker under `~/.config/trading-stats-tracker` or add `alert_configs/active_config.json` to `.gitignore`.

---

### 10. Loss of Win/Loss Duration Context
**Location**: `trade_stats_processor.py:700-748`, `alert_configs/presets/default.json:150-170`  
**Severity**: Medium  
**Status**: Unfixed

**Problem**: The JSON context only exposes `win_avg_secs_vs_loss_avg_secs`, but it is populated with `win_avg_secs.total_seconds()` (no loss component). The default preset attempts to implement the legacy rule “warn when winning trades take longer than losing trades” using `"when": "win_avg_secs_vs_loss_avg_secs < 60"`, which no longer compares win vs loss durations. We’ve lost the original behavior, and JSON configs cannot express it.

**Impact**: The “Short Winning Trade Duration” alert fires based on an absolute 60‑second threshold instead of comparing win/loss durations, so it can miss or falsely trigger warnings.  
**Fix**: Publish both win and loss averages (or their ratio) to the context so JSON can compare them. Update presets accordingly.

---

### 11. `validate` Command Changes Active Profile
**Location**: `manage_alert_configs.py:66-96`, `alert_config_manager.py:157-209`  
**Severity**: Medium  
**Status**: Unfixed

**Problem**: `manage_alert_configs.py validate` loops through `manager.load_config(name)` for every profile. `load_config()` updates `self.current_profile_name` and caches the loaded profile, so running validation silently switches the active profile to the last one validated.

**Impact**: Developers’ active profile is overwritten whenever they run the validate command, leading to surprising config changes or alerts.  
**Fix**: Validate by reading files directly (without calling `load_config`) or use a fresh manager per profile so the user’s active selection isn’t modified.

---

## Additional Type Checking Errors

### 12. Type Safety Issues in Trade Stats Processing
**Location**: `trade_stats_processor.py:246-247, 261, 287-288, 297, 559, 584, 672`  
**Severity**: Medium  
**Status**: Unfixed

**Problems Found**:
- Line 246-247: Operator "+=" not supported for types "float | Unknown" and "Unknown | str | int"
- Line 261: Operator "*" not supported for types "float" and "str | int"
- Line 287-288: Argument type mismatches for trade_size and trade_value parameters
- Line 297: Argument type mismatch for trade_amount parameter
- Lines 559, 584, 672: "position_size" is possibly unbound

**Impact**: Runtime type errors and potential crashes  
**Fix**: Add proper type annotations and type checking

### 11. None Attribute Access in App UI
**Location**: `app.py:412, 415, 148`  
**Severity**: Medium  
**Status**: Unfixed

**Problems Found**:
- Line 412: Cannot access attribute "setText" for class "None"
- Line 415: Cannot access attribute "setStyleSheet" for class "None"
- Line 148: "deleteLater" is not a known attribute of "None"

**Impact**: UI crashes when widgets are None  
**Fix**: Add proper None checks before accessing widget attributes

---

## Recommended Fixes Priority Order

1. **Fix the None return bug** in alert config manager initialization (Critical)
2. **Replace eval()** with a safe expression evaluator (Critical)
3. **Add proper error handling** for aggregated account alert generation (Critical)
4. **Implement logging** for dropped alerts (Critical)
5. **Add comprehensive tests** for error scenarios (Medium)
6. **Create fallback mechanisms** when JSON config fails to load (Medium)
7. **Fix group-based filtering logic** to clarify intended behavior (Medium)
8. **Improve path resolution** with better error handling (Medium)
9. **Implement cache invalidation** strategies (Medium)
10. **Fix variable naming** for code clarity (Low)

---

## Testing Recommendations

1. **Add error scenario tests** for all identified bugs
2. **Create integration tests** for alert config manager initialization failures
3. **Add security tests** for expression evaluation
4. **Test aggregated account processing** with various failure modes
5. **Verify fallback behavior** when JSON config is unavailable

---

## Files Modified in This Branch

- `alert_config_manager.py` (347 lines added)
- `trade_stats_processor.py` (961 lines added/modified)
- `app.py` (258 lines added/modified)
- `manage_alert_configs.py` (156 lines added)
- Test files (8 test files, 1732 lines added)
- Configuration files (schemas, presets)
- Documentation files

---

## Conclusion

The JSON Alert Configuration implementation is well-structured with good test coverage, but these bugs could cause runtime failures that would be hard to debug in production. The security vulnerability and potential for silent alert loss are particularly concerning and should be addressed immediately.

The implementation shows good architectural thinking with proper separation of concerns, but error handling and security considerations need significant improvement before this can be considered production-ready.
