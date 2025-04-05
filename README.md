# trading-stats-tracker
get more frequent trading stats by reading MotiveWave logs

# hammerspoon pre-requisites
hammerspoon is used on two key features
1. alerts (uses hs.alert) - requires hs cli
2. disabling MotiveWave on critical alerts (tilt conditions)

you can disable alerts by setting in config.py `self.alert_enabled = False`

you can disable blocking of MotiveWave by setting in config.py `self.block_app_on_critical_alerts = False`

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