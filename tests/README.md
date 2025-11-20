# JSON Alert Config - Essential Tests

This directory contains comprehensive tests for the JSON Alert Config system implementation.

## Test Coverage

### 1. AlertConfigManager Tests (`test_alert_config_manager.py`)
- ✅ Profile discovery and loading
- ✅ Schema validation and error handling  
- ✅ Configuration caching
- ✅ Session overrides integration
- ✅ Profile copying and saving with backups
- ✅ Error handling for missing/invalid files

### 2. ConditionEvaluator Tests (`test_condition_evaluator.py`)
- ✅ Expression evaluation with safe AST execution
- ✅ Group-based short-circuit evaluation (first match wins)
- ✅ Disabled condition filtering
- ✅ Multiple group handling
- ✅ Error recovery for invalid expressions
- ✅ Concern level mapping and message formatting
- ✅ Complex boolean logic evaluation

### 3. Integration Tests (`test_integration.py`)
- ✅ TradeStatsProcessor integration with JSON config
- ✅ Automatic fallback to legacy alerts on JSON failure
- ✅ Alert message creation from evaluator results
- ✅ Context field validation
- ✅ Config manager initialization and error handling

### 4. CLI Tools Tests (`test_cli_tools.py`)
- ✅ Profile listing and discovery
- ✅ Configuration validation
- ✅ Profile cloning and creation
- ✅ Active profile management
- ✅ Error handling for CLI commands
- ✅ Export functionality

## Running Tests

### Quick Test Run
```bash
python run_tests.py
```

### Individual Test Files
```bash
# Test AlertConfigManager
python -m pytest tests/test_alert_config_manager.py -v

# Test ConditionEvaluator  
python -m pytest tests/test_condition_evaluator.py -v

# Test Integration
python -m pytest tests/test_integration.py -v

# Test CLI Tools
python -m pytest tests/test_cli_tools.py -v

# Run all tests
python -m pytest tests/ -v
```

## Test Data

Test fixtures are located in `tests/fixtures/test_data.py`:
- Valid and invalid configuration examples
- Test alert contexts with all required fields
- JSON schema for validation
- Context data for triggering/not triggering conditions

## What These Tests Verify

### Core Functionality ✅
- JSON configs load and validate correctly
- Alert conditions evaluate properly with real context data
- Fallback to legacy alerts works when JSON system fails
- All CLI commands function correctly
- Session overrides integrate properly

### Error Handling ✅
- Missing or invalid config files are handled gracefully
- Schema validation failures don't crash the system
- Invalid expressions don't break alert evaluation
- CLI errors provide helpful feedback

### Integration ✅
- TradeStatsProcessor seamlessly uses JSON configs
- Alert messages are created correctly from evaluator output
- Context fields are properly provided and validated
- System maintains backward compatibility

## Production Readiness

These tests ensure that the JSON Alert Config system:
1. **Works correctly** - All core functionality is tested and verified
2. **Handles errors gracefully** - Robust error handling prevents crashes
3. **Maintains compatibility** - Fallback mechanisms ensure system stability
4. **Provides good UX** - CLI tools work as expected with proper error messages

The test suite covers the essential functionality that was missing from the original implementation, providing confidence that the JSON Alert Config system is production-ready and can safely replace the hardcoded conditions.