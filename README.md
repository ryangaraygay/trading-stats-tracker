# trading-stats-tracker
get more frequent trading stats by reading MotiveWave logs

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