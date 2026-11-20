# Experimental validation record — 2026-11-20

This is an implementation/test record, not a physical printer calibration.

- Automated suite: `python -m unittest discover -s tests -v`.
- Windows development environment: 36 tests passed; two Linux installer tests
  were skipped. GitHub Actions runs the complete suite on Ubuntu.
- Actual upstream Klipper G-code parameter parsing and native `save_variables`
  writing/reloading were exercised offline with a generated calibration command.
  The coefficient and metadata round-tripped together; unrelated variables and
  the user offset were preserved. No printer connection was used.
- All KAT G-code templates were compiled with Klipper-style Jinja delimiters.
- Physical probing, surface suitability, temperature-cycle repeatability and
  first-layer outcomes with this extra have **not** been verified. Home-machine
  trials are the next step. The earlier fixed-offset Herkules trial does not
  validate this temperature experiment.

Primary Klipper source hashes used in the offline protocol check:

| Source | SHA-256 |
|---|---|
| `klippy/gcode.py` | `a2bcd6949b4263f608eaa71ba1cdfb713553542b7b90de739241b624f06415ae` |
| `klippy/extras/save_variables.py` | `ddd23fbca8634bb7c1e14314c80be455db6003d0c8d469b4eddc50e75da23d28` |

Sources: [Klipper parser](https://github.com/Klipper3d/klipper/blob/master/klippy/gcode.py),
[variables writer](https://github.com/Klipper3d/klipper/blob/master/klippy/extras/save_variables.py),
[Beacon probing](https://github.com/beacon3d/beacon_klipper/blob/master/beacon.py),
[RatOS measurement sequence](https://github.com/Rat-OS/RatOS-configurator/blob/v2.1.x/configuration/z-probe/beacon.cfg).
