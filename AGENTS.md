# Agent Guidelines for Trading Stats Tracker

## Commands

### Build & Install
```bash
make install          # Install dependencies from requirements.txt
make run              # Run application: python app.py
make run_local        # Run with local config: CONFIG_ENV=local python app.py
```

### Development
```bash
make format           # Format code with black *.py
make lint             # Lint with pylint (currently commented)
make test             # Run tests with pytest (currently commented)
make test_resource_usage  # Profile with scalene app.py
make all              # Run install → lint → test
```

### Single Test Execution
```bash
# Since pytest is commented in Makefile, run directly:
python -m pytest -vv test_filename.py
# Or for specific test:
python -m pytest -vv test_filename.py::test_function_name
```

## Code Style Guidelines

### Imports & Organization
- Group imports: stdlib → third-party → local modules
- Use alphabetical ordering within groups
- Example: `import sys` → `from PyQt6.QtWidgets import QApplication` → `from config import Config`

### Formatting & Naming
- Follow PEP 8 (enforced by `black *.py`)
- Constants: `UPPER_CASE` (e.g., `CONST`, `DAY_TIME_FORMAT`)
- Classes: `PascalCase` (e.g., `ConcernLevel`, `TradingStatsApp`)
- Functions/variables: `snake_case` (e.g., `get_alert_duration`, `config_dir`)
- Use type hints: `def get_alert_duration(self, level: ConcernLevel) -> str:`

### Data Structures
- Prefer `namedtuple` for simple data structures (see `trade.py:3`)
- Use `Enum` for related constants with ordering (see `concern_level.py:3`)
- Use `IntEnum` when numeric ordering matters

### Error Handling
- Use try/catch blocks for config parsing (see `config.py:79-92`)
- Provide meaningful error messages with fallbacks
- Handle missing configuration files gracefully

### Configuration
- Use `configparser.ConfigParser()` for .ini files
- Support environment-specific configs via `CONFIG_ENV`
- Provide default values with `get_bool()`, `get_int()` helpers

### Documentation
- Add docstrings for functions (see `my_utils.py:4-16`)
- Comment complex logic (see `config.py:26-29`)
- Use descriptive variable names over inline comments

### Dependencies
- Keep minimal: only `pynput`, `scalene` in requirements.txt
- Use PyQt6 for GUI components
- Follow existing import patterns in `app.py:1-19`

### Testing
- Place tests in root directory (following Makefile pattern)
- Use pytest with `-vv` flag for verbose output
- Mock external dependencies where possible

### Performance
- Use `scalene` profiler for performance analysis
- Minimize GUI refresh operations
- Cache computed data when possible (see `config.py:23-24`)
- GUI note: when refreshing layouts in `app.py`, do NOT delete `self.profile_status_label` (or other persistent widgets). Removing it breaks PyQt references and causes “wrapped C/C++ object … has been deleted” runtime errors.
