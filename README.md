# KAT – Klipper Automation Toolkit

KAT is a macro and workflow toolkit for Klipper and Kalico.

The goal is not to replace your printer configuration. Your `printer.cfg` should still describe what the machine is: motors, heaters, probes, fans, sensors, kinematics, limits, and hardware-specific behavior.

KAT defines how the machine is used.

It provides a consistent operating layer for start print, end print, pause/resume, material-aware behavior, air handling, safe parking, calibration helpers, and resonance graph tooling.

---

## Core idea

Firmware gives us the possibilities.

KAT should be the standardized way we use them.

KAT is designed around one principle:

```text
printer.cfg = what the machine is
KAT         = how the machine is operated
```

This means KAT should work across many different Klipper/Kalico machines without requiring every user to rewrite the same basic macros from scratch.

---

## Requirements

KAT expects a reasonably modern Klipper or Kalico setup.

### Required

* `[respond]`
* `[pause_resume]`
* `[display_status]`
* `gcode_shell_command`

`gcode_shell_command` is treated as a standard KAT requirement. KAT will use it for built-in tooling such as input shaper and belt tension graph generation from the UI/console.

### Recommended

* `[bed_mesh]`
* `QUAD_GANTRY_LEVEL` or `Z_TILT_ADJUST`, where applicable
* Filament sensors, where applicable
* A clearly defined nozzle wipe macro if using nozzle-based probing

---

## What KAT should handle

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

Important behavior:

* The bed is heated early with `M190` before homing, leveling, probing, and meshing.
* QGL or Z Tilt is selected automatically if available.
* Z is always re-homed after QGL/Z Tilt because the reference plane has changed.
* Beacon gets its own contact calibration path.
* Other probes use normal `G28 Z`, allowing the printer configuration to decide how Z homing works.
* Optional nozzle wipe can be enabled before the final Z home for TAP, piezo, Beacon contact, or other nozzle-based probing systems.

### PAUSE / RESUME / CANCEL

KAT pause handling is designed for real print recovery:

* Save hotend target temperature.
* Save part cooling fan speed.
* Pause using Klipper's native pause state.
* Retract only when the extruder can actually extrude.
* Use safe Z-hop and named park helpers.
* Restore hotend temperature before resuming motion.
* Restore part cooling fan before resuming motion.
* Restore pause retract if one was applied.
* Check enabled filament switch sensors before resume.
* Avoid automatic load/unload behavior unless the user explicitly builds that into their own workflow.

### END_PRINT

KAT end print handling should use shared helpers rather than duplicating movement logic:

* Turn off heaters safely.
* Retract if possible.
* Move Z to a safe end-print height.
* Park the toolhead using a named park position.
* Turn off part cooling.
* Handle filter and exhaust helpers.
* Restore idle timeout.
* Clear KAT print state.

### Resonance and belt tooling

KAT should include graph generation as a standard feature, not as an afterthought.

Planned standard commands:

```ini
KAT_GENERATE_SHAPER_GRAPH_X
KAT_GENERATE_SHAPER_GRAPH_Y
KAT_GENERATE_BELT_TENSION_GRAPH
```

These commands should use `gcode_shell_command` to run KAT shell scripts that generate PNG graphs from Klipper resonance CSV files.

Expected output location:

```text
~/printer_data/config/input_shaper/
```

KAT should report the created graph path in the console after generation.

Whether the image can be opened directly from the UI depends on the frontend and how the file browser exposes the output folder, but graph generation itself should be available from the normal KAT workflow.

---

## Current project structure

The working structure is centered around the `KAT/` folder:

```text
KAT/
    variables.cfg              Shared KAT variables and user settings
    temperature_control.cfg    Temperature command overrides and helpers
    start_macro.cfg            START_PRINT and start-related helpers
    pause_resume.cfg           PAUSE, RESUME, CANCEL_PRINT and filament events
    helpers.cfg                Shared movement, homing, park, and safety helpers
    end_macro.cfg              END_PRINT flow
    filter.cfg                 Filter and exhaust helpers
    prime.cfg                  Prime and wipe helpers
    resonance_tools.cfg        Input shaper and belt graph commands

scripts/
    kat-common.sh
    generate-shaper-graph-x.sh
    generate-shaper-graph-y.sh
    generate-belt-tension-graph.sh

docs/
    usage and design notes
```

Some files may still be work in progress while the core architecture is being finalized.

---

## Installation concept

The intended include style is:

```ini
[include KAT/variables.cfg]
[include KAT/temperature_control.cfg]
[include KAT/helpers.cfg]
[include KAT/filter.cfg]
[include KAT/prime.cfg]
[include KAT/start_macro.cfg]
[include KAT/end_macro.cfg]
[include KAT/pause_resume.cfg]
[include KAT/resonance_tools.cfg]
```

The exact include list may change while the project is still being structured.

---

## Configuration philosophy

KAT uses one shared variable macro:

```ini
[gcode_macro KAT]
```

User-adjustable values should live there.

Examples:

```ini
variable_default_material: '"PLA"'
variable_start_preheat_temp: 150.0
variable_start_preheat_minutes: 0.0
variable_start_wipe_before_z_home: False
variable_pause_park_position: '"front_center"'
variable_end_print_park_position: '"front_center"'
```

The goal is that users should not need to edit the logic macros for normal configuration.

---

## Design principles

### Do not duplicate firmware functionality

If Klipper already has a proper firmware-level feature, KAT should not rebuild it in macros.

Examples:

* Axis twist compensation should use Klipper's `[axis_twist_compensation]` module.
* Bed mesh should use Klipper's `[bed_mesh]` module.
* QGL and Z Tilt should use Klipper's native mechanisms.

KAT should orchestrate these features, not replace them.

### Let the printer config own hardware behavior

KAT should not try to take over every hardware-specific detail.

For example:

* If a machine has `[homing_override]`, KAT should respect it.
* If a machine has a custom wipe routine, KAT should call it, not hardcode wiper coordinates.
* If a machine has Beacon, KAT can use Beacon-specific commands.
* If a machine does not have Beacon, KAT should fall back to standard Klipper behavior.

### Prefer helpers over duplicated math

Shared calculations should live in helpers:

* safe Z-hop
* named park positions
* end-print Z movement
* conditional homing
* park feedrate calculation

Print macros should orchestrate the flow, not recalculate everything themselves.

### Be informative, not annoying

KAT should provide useful console messages, especially when something is skipped because the printer does not have that capability.

Examples:

```text
No QGL or Z_TILT configured, skipping
No bed_mesh configured, skipping
FILTER_ON not found, skipping
```

### Avoid unwanted automatic filament movement

KAT should not automatically load, unload, purge, or perform aggressive filament handling unless the user explicitly configures that behavior.

Sensors should report events. KAT should pause, save state, inform the user, and resume safely.

---

## Roadmap

### Core

* Shared KAT variables
* Temperature control helpers
* START_PRINT
* END_PRINT
* PAUSE / RESUME / CANCEL_PRINT
* Safe movement helpers
* Filter and exhaust helpers
* Prime and wipe helpers

### Tooling

* Input shaper graph generation
* Belt tension graph generation
* UI/console macros using `gcode_shell_command`

### Later

* Layer pause helpers
* Calibration helpers
* Better documentation examples
* Example slicer start/end gcode
* Example printer configurations

---

## Status

KAT is in early development.

The architecture is being defined and core files are being built step by step.

Expect changes while the project is still moving toward a stable first release.
