# Tech Debt – JSON Alert Configuration

Items here are enhancements or intentional behaviors that were previously misclassified as “bugs”.

### TD‑001 – Expression Evaluation Uses `eval`
**Location:** `alert_config_manager.py:306-311`  
**Status:** Known limitation  
**Notes:** Users control their JSON configs, so the `eval` usage is acceptable today. Long term we may want a safer expression parser if profiles become shareable.

### TD‑002 – Group Short-Circuit Logic
**Location:** `alert_config_manager.py:320-336`  
**Status:** Intentional  
**Notes:** Only the first matching condition per group fires to mirror the legacy behavior. Change only if requirements shift.

### TD‑003 – Schema Missing → Warning Only
**Location:** `alert_config_manager.py:72-99`  
**Status:** Intentional fallback  
**Notes:** Logging a warning and proceeding without validation is acceptable; no hard failure is needed.

### TD‑004 – Cache Invalidation
**Location:** `alert_config_manager.py:185-200`  
**Status:** Future enhancement  
**Notes:** Config caching assumes manual reload triggers. Add invalidation once hot‑reload is required.

### TD‑005 – Variable Naming (`exc_field`)
**Location:** `alert_config_manager.py:134`  
**Status:** Cosmetic  
**Notes:** Rename for clarity when convenient; no functional impact.

### TD‑006 – Type-Checker Warnings
**Location:** `trade_stats_processor.py` (various)  
**Status:** Low priority  
**Notes:** Pyright/mypy warnings stem from dynamic data structures. Address when adding type hints, but they aren’t runtime bugs.
