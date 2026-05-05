# KAT – Klipper Automation Toolkit

KAT is a macro and workflow toolkit for Klipper and Kalico.

The goal is not to replace your printer configuration. Your `printer.cfg` should still describe what the machine is: motors, heaters, probes, fans, sensors, kinematics, limits, and hardware-specific behavior.

KAT defines how the machine is used.

```text
printer.cfg = what the machine is
KAT         = how the machine is operated
```

---

## Installation

The recommended installation keeps the full Git repository on the machine, while exposing only the actual KAT config folder to Klipper.

This gives the user a clean include path and still allows KAT to be updated through Git or Moonraker.

### 1. Clone KAT

SSH into the printer host and run:

```bash
cd ~/printer_data/config
git clone https://github.com/HjortCreations/klipper_KAT.git
```

### 2. Create the KAT symlink

Create a symlink so Klipper can include KAT using a clean path:

```bash
ln -sfn klipper_KAT/KAT KAT
```

Expected layout:

```text
~/printer_data/config/
├─ printer.cfg
├─ klipper_KAT/          <- full Git repository
│  ├─ README.md
│  ├─ moonraker_example.cfg
│  └─ KAT/
│     ├─ core_features.cfg
│     ├─ variables.cfg
│     ├─ start_macro.cfg
│     ├─ pause_resume.cfg
│     └─ scripts/
└─ KAT -> klipper_KAT/KAT
```

### 3. Include KAT in `printer.cfg`

Add this single line to your existing `printer.cfg`:

```ini
[include KAT/core_features.cfg]
```

Restart Klipper.

---

## Advanced features

Core KAT can run without advanced shell-based features.

Advanced features require `gcode_shell_command`.

Advanced features currently include:

```text
KAT_TEST_SHELL_COMMAND
KAT_TEST_RESONANCES_X
KAT_TEST_RESONANCES_Y
KAT_TEST_RESONANCES_Z
KAT_GENERATE_BELT_TENSION_GRAPH
```

To enable advanced features, open:

```text
~/printer_data/config/KAT/core_features.cfg
```

and uncomment:

```ini
#[include KAT/advanced_features.cfg]
```

so it becomes:

```ini
[include KAT/advanced_features.cfg]
```

If Klipper fails to load with an error about `[gcode_shell_command ...]`, install `gcode_shell_command` before enabling advanced features.

Reference:

```text
https://github.com/th33xitus/kiauh/blob/master/docs/gcode_shell_command.md
```

After enabling advanced features and restarting Klipper, test shell command support from the console:

```ini
KAT_TEST_SHELL_COMMAND
```

---

## Moonraker update manager

KAT can be added to Moonraker's update manager.

Copy the section from:

```text
moonraker_example.cfg
```

into your `moonraker.conf`.

Expected update-manager path:

```text
~/printer_data/config/klipper_KAT
```

After editing `moonraker.conf`, restart Moonraker.

---

## Requirements

KAT expects a reasonably modern Klipper or Kalico setup.

Core KAT provides and uses common Klipper modules such as:

```ini
[respond]
[pause_resume]
[display_status]
[virtual_sdcard]
[force_move]
[idle_timeout]
[exclude_object]
[skew_correction]
[gcode_arcs]
```

Advanced features require:

```text
gcode_shell_command
```

Resonance graph generation also requires machine-specific resonance configuration in `printer.cfg`, normally including:

```ini
[resonance_tester]
```

and an accelerometer configuration such as:

```ini
[adxl345]
```

or equivalent.

KAT does not define accelerometers or resonance tester hardware. That remains machine-specific and belongs in `printer.cfg`.

---

## What KAT handles

### START_PRINT

KAT provides a capability-aware start flow:

```text
bed heat and optional heat soak
material state
filter / exhaust behavior
MAYBE_HOME
KAT_LEVEL_GANTRY
KAT_WIPE_BEFORE_Z_HOME
KAT_HOME_Z_AFTER_LEVEL
KAT_BED_MESH
final nozzle heat
prime / wipe
```

### PAUSE / RESUME / CANCEL

KAT pause handling is designed for real print recovery:

- Save hotend target temperature.
- Save part cooling fan speed.
- Pause using Klipper's native pause state.
- Retract only when the extruder can actually extrude.
- Use safe Z-hop and named park helpers.
- Restore hotend temperature before resuming motion.
- Restore part cooling fan before resuming motion.
- Restore pause retract if one was applied.
- Check enabled filament switch sensors before resume.
- Avoid automatic load/unload behavior unless the user explicitly configures that behavior.

### END_PRINT

KAT end print handling uses shared helpers rather than duplicating movement logic:

- Turn off heaters safely.
- Retract if possible.
- Move Z to a safe end-print height.
- Park the toolhead using a named park position.
- Turn off part cooling.
- Handle filter and exhaust helpers.
- Restore idle timeout.
- Clear KAT print state.

### Resonance and belt tooling

When advanced features are enabled, KAT can run resonance tests and generate graphs from the UI/console:

```ini
KAT_TEST_RESONANCES_X
KAT_TEST_RESONANCES_Y
KAT_TEST_RESONANCES_Z
KAT_GENERATE_BELT_TENSION_GRAPH
```

Expected output location:

```text
~/printer_data/config/input_shaper/
```

If `[resonance_tester]` is not configured, KAT prints a help message and points to:

```text
https://www.klipper3d.org/Measuring_Resonances.html
```

---

## Current project structure

The runtime Klipper configuration is centered around the `KAT/` folder:

```text
KAT/
    core_features.cfg          Main KAT core entrypoint
    klipper_features.cfg       Baseline Klipper modules used by KAT
    variables.cfg              Shared KAT variables and user settings
    temperature_control.cfg    Temperature command overrides and helpers
    helpers.cfg                Shared movement, homing, park, and safety helpers
    filter.cfg                 Filter and exhaust helpers
    prime.cfg                  Prime and wipe helpers
    start_macro.cfg            START_PRINT and start-related helpers
    end_macro.cfg              END_PRINT flow
    pause_resume.cfg           PAUSE, RESUME, CANCEL_PRINT and filament events
    advanced_features.cfg      Shell-command based advanced features
    resonance_tools.cfg        Resonance and belt graph commands
    scripts/                   Shell scripts used by advanced features
```

The repository root may also contain documentation, examples, update-manager examples, and installation helpers.

Those files are not included directly by Klipper.

---

## Configuration philosophy

KAT uses one shared variable macro:

```ini
[gcode_macro KAT]
```

User-adjustable values should live there.

The goal is that users should not need to edit the logic macros for normal configuration.

---

## Design principles

KAT should orchestrate Klipper features, not replace them.

Machine-specific hardware behavior should stay in `printer.cfg` or separate machine config files.

KAT should provide useful console messages when something is skipped because the printer does not have that capability.

KAT should not automatically load, unload, purge, or perform aggressive filament handling unless the user explicitly configures that behavior.

---

## Status

KAT is in early development.

The architecture is being defined and core files are being built step by step.

Expect changes while the project is still moving toward a stable first release.
