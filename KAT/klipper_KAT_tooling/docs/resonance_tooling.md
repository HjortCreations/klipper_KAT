# KAT resonance tooling

This optional tooling helps generate input shaper and belt tension graphs from Klipper resonance CSV files.

## Files

```text
scripts/kat-common.sh
scripts/generate-shaper-graph-x.sh
scripts/generate-shaper-graph-y.sh
scripts/generate-belt-tension-graph.sh
optional/shell_commands.cfg
```

## Default paths

The scripts assume a common Klipper/Moonraker setup:

```text
~/printer_data
~/klipper
~/printer_data/config/input_shaper
```

These can be overridden with environment variables:

```bash
KAT_PRINTER_DATA_DIR=/home/pi/printer_data
KAT_KLIPPER_DIR=/home/pi/klipper
KAT_OUTPUT_DIR=/home/pi/printer_data/config/input_shaper
```

## Manual usage over SSH

After running the relevant Klipper resonance test, run:

```bash
./scripts/generate-shaper-graph-x.sh
./scripts/generate-shaper-graph-y.sh
./scripts/generate-belt-tension-graph.sh
```

Make scripts executable first:

```bash
chmod +x scripts/*.sh
```

## Optional Klipper macro usage

Only use `optional/shell_commands.cfg` if your Klipper install has `gcode_shell_command` support.

Example include:

```ini
[include KAT/optional/shell_commands.cfg]
```

Then run from the console:

```ini
KAT_GENERATE_SHAPER_GRAPH_X
KAT_GENERATE_SHAPER_GRAPH_Y
KAT_GENERATE_BELT_TENSION_GRAPH
```

## Notes

The belt tension script waits 10 seconds before reading CSV files because resonance commands may return before all CSV data is fully written.
