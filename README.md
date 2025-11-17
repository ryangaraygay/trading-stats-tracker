# trading-stats-tracker
get more frequent trading stats by reading MotiveWave logs

# Alert configuration
The alert system now reads from JSON profiles instead of hard-coded thresholds. Config files live in `alert_configs/` and are organized as:

```
alert_configs/
├── presets/                    # shipped defaults (e.g., default.json, demo-aggressive.json)
├── user/                       # gitignored, for your custom copies
├── backups/                    # automatic timestamps from saves
└── schemas/alert_config.schema.json
```

`AlertConfigManager` merges configs in this order: user directory → optional `CONFIG_ENV` preset → repo preset. The active profile can also be forced via `ALERT_CONFIG_NAME`, `alert_configs/active_config.json`, or the future UI dropdown. Runtime-only overrides (via UI sliders or toggles) exist only in memory for the current session; nothing is persisted or exposed to CLI besides cloning and saving new profiles.

Manage profiles with the helper script:

```bash
python manage_alert_configs.py list
python manage_alert_configs.py clone default focus_mode
python manage_alert_configs.py set-active focus_mode
python manage_alert_configs.py export-hardcoded ~/Downloads/default_alert.json
python manage_alert_configs.py validate
```

`make validate_alerts` (added alongside `make format`) runs the same schema checks over every profile.

# hammerspoon pre-requisites
hammerspoon is used on two key features
1. alerts (uses hs.alert) - requires hs cli
2. disabling MotiveWave on critical alerts (tilt conditions)

you can disable alerts by setting in config.ini
```
[alert]
enabled = False
```

you can disable blocking of MotiveWave by setting in config.ini
```
[alert]
block_app_on_critical_alerts = False
```

hammerspoon must be running for these to work

enabling alerts only requires hs cli whereas enabling blocking of MW requires some hammerspoon lua code in your own init.lua
see https://github.com/ryangaraygay/hammerspoon-scripts/blob/main/init.lua

# testing performance
```
python -m cProfile -o profile_output.out app.py
```
## visualize
```
pip install snakeviz
snakeviz profile_output.out
```
## line level profiling (if needed)
```
pip install line_profiler
```

add function decorator `@profile` to the function you want to profile

execute and analyze
```
kernprof -l app.py
python -m line_profiler app.py.lprof
```
