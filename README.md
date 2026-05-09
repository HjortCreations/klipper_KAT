# KAT – Klipper Automation Toolkit

KAT is a macro and workflow toolkit for Klipper and Kalico.

The goal is not to replace your printer configuration. Your `printer.cfg` should still describe what the machine is: motors, heaters, probes, fans, sensors, kinematics, limits, and hardware-specific behavior.

KAT defines how the machine is used.

```text
printer.cfg = what the machine is
KAT         = how the machine is operated
```

Firmware gives us the possibilities. KAT should be the standardized way we use them.

---

## What KAT is

KAT is an operating layer for Klipper/Kalico printers.

It is designed to make common printer workflows more consistent, reusable, and easier to maintain across different machines and printer configurations.

KAT focuses on:

- START_PRINT
- END_PRINT
- PAUSE / RESUME / CANCEL_PRINT
- safe parking and movement helpers
- material-aware print preparation
- filter and exhaust helpers
- prime and wipe helpers
- resonance and belt graph tooling
- clear console feedback when features are missing or skipped

KAT should orchestrate existing Klipper/Kalico features, not replace the printer's hardware configuration.

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
│  ├─ include_example.cfg
│  ├─ moonraker_example.cfg
│  └─ KAT/
│     ├─ core_features.cfg
│     ├─ variables.cfg
│     ├─ start_print.cfg
│     ├─ pause_resume.cfg
│     ├─ end_print.cfg
│     ├─ kat_helpers.cfg
│     └─ scripts/
└─ KAT -> klipper_KAT/KAT
```

### 3. Include KAT in `printer.cfg`

Add this single line to your existing `printer.cfg`:

```ini
[include KAT/core_features.cfg]
```

Restart Klipper.

### 4. Configure slicer START_PRINT parameters

KAT reads these parameters from your slicer start G-code:

**Recommended (send these):**

- `EXTRUDER_TEMP` (first-layer nozzle temp)
- `BED_TEMP` (first-layer bed temp)
- `MATERIAL` (for airflow/material behavior, e.g. `PLA`, `PETG`, `ABS`)

**Optional:**

- `EXTRUDER_TEMP_OTHER` (stored by KAT for tooling/telemetry use)
- `PREHEAT_MINUTES` (extra bed/chamber soak time after bed reaches target)

If a value is missing, KAT uses safe defaults from `KAT/variables.cfg` (or built-in defaults).

Example start G-code line in slicer:

```gcode
START_PRINT EXTRUDER_TEMP=[first_layer_temperature] BED_TEMP=[first_layer_bed_temperature] MATERIAL=[filament_type]
```

Optional extended example:

```gcode
START_PRINT EXTRUDER_TEMP=[first_layer_temperature] EXTRUDER_TEMP_OTHER=[nozzle_temperature] BED_TEMP=[first_layer_bed_temperature] MATERIAL=[filament_type] PREHEAT_MINUTES=10
```

---

## Updating KAT

If KAT was installed using the recommended Git clone method, it can be updated with:

```bash
cd ~/printer_data/config/klipper_KAT
git pull
```

After updating, restart Klipper.

KAT can also be added to Moonraker's update manager. See the `moonraker_example.cfg` file in this repository.

---

## Moonraker update manager

KAT can be added to Moonraker's update manager.

Add this section directly to your `moonraker.conf`:

```ini
[update_manager klipper_KAT]
type: git_repo
path: ~/printer_data/config/klipper_KAT
origin: https://github.com/HjortCreations/klipper_KAT.git
primary_branch: main
managed_services: klipper
```

Then restart Moonraker:

```bash
sudo systemctl restart moonraker
```

Quick check after restart:

- Open Mainsail/Fluidd and verify `klipper_KAT` appears in Update Manager.
- Run `ls -l ~/printer_data/config/KAT` and verify the symlink points to `klipper_KAT/KAT`.

If you prefer, the same block is also available in `moonraker_example.cfg`.


---

## Safe onboarding (test without printing)

Before using KAT in a real print, run these dry tests from the console.

### Phase 1: cold motion-only test

1. `G28`
2. `PARK_TOOLHEAD POSITION=front_center`
3. `END_PRINT`

### Phase 2: pause/resume behavior test

1. `PAUSE`
2. `RESUME`

Recommended setup for both phases:

- No active print file
- Start with a cold nozzle and no filament loaded
- Keep one hand near emergency stop/power

After Phase 1 and 2 pass, you can run a final heated check if desired.

If any move is not suitable for your machine, tune KAT variables first in `KAT/variables.cfg`, especially park positions, margins, pause Z-hop, and resume filament check mode.

---

## Core and advanced features

KAT is split into core and advanced features.

### Core features

Core features are loaded by:

```ini
[include KAT/core_features.cfg]
```

Core KAT includes the normal print workflow and helper macros.

### Advanced features

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

## Recommended machine-specific features

KAT can use these features when available:

```text
[bed_mesh]
[quad_gantry_level]
[z_tilt]
[resonance_tester]
filament sensors
custom nozzle wipe macros
Beacon / TAP / piezo / other probe systems
```

KAT should orchestrate these features, not replace the printer's hardware configuration.

---

## Expected fan and sensor names

Some KAT helpers look for standard names.

### Filter fan

KAT expects the filter fan to be named:

```ini
[fan_generic filter]
```

Used by:

```text
FILTER_ON
FILTER_OFF
START_PRINT / END_PRINT helpers when available
```

### Exhaust fan

KAT expects the exhaust fan to be named:

```ini
[fan_generic exhaust]
```

Used by:

```text
EXHAUST_ON
EXHAUST_OFF
START_PRINT / END_PRINT helpers when available
```

### Filament events

KAT expects filament sensors to call KAT event macros instead of letting the sensor directly pause the printer.

Example runout behavior:

```ini
runout_gcode:
    FILAMENT_RUNOUT
```

Example clog behavior:

```ini
runout_gcode:
    FILAMENT_CLOG
```

See `include_example.cfg` for examples.

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

Important behavior:

- The bed is heated early with `M190` before homing, leveling, probing, and meshing.
- QGL or Z Tilt is selected automatically if available.
- Z is always re-homed after QGL/Z Tilt because the reference plane has changed.
- Beacon gets its own contact calibration path where applicable.
- Other probes use normal `G28 Z`, allowing the printer configuration to decide how Z homing works.
- Optional nozzle wipe can be enabled before the final Z home for TAP, piezo, Beacon contact, or other nozzle-based probing systems.

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

## KAT status and version information

KAT may expose a small status/about command such as:

```ini
KAT_ABOUT
```

A quick sanity check command is also available:

```ini
KAT_SELFTEST
```

`KAT_SELFTEST` reports whether `PARK_TOOLHEAD`, `SAFE_PAUSE_Z_HOP`, and `END_PRINT` are loaded, which resume filament check mode is active, and how many `filament_switch_sensor` sections are found/enabled.

A typical console message can look like:

```text
KAT 0.4.0-dev active
Klipper Automation Toolkit
Sponsored and maintained by Hjort Creations
Repository: https://github.com/HjortCreations/klipper_KAT
```

This makes it easier to confirm that KAT is loaded and helps with support and troubleshooting.

---

## Current project structure

The runtime Klipper configuration is centered around the `KAT/` folder:

```text
KAT/
    about.cfg                  KAT status/about command
    core_features.cfg          Main KAT core entrypoint
    klipper_features.cfg       Baseline Klipper modules used by KAT
    variables.cfg              Shared KAT variables and user settings
    temperature_control.cfg    Temperature command overrides and helpers
    fan_control.cfg            Filter and exhaust helpers
    kat_helpers.cfg            Shared movement, homing, park, and safety helpers
    prime.cfg                  Prime and wipe helpers
    start_print.cfg            START_PRINT and start-related helpers
    end_print.cfg              END_PRINT flow
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

- Axis twist compensation should use Klipper's `[axis_twist_compensation]` module.
- Bed mesh should use Klipper's `[bed_mesh]` module.
- QGL and Z Tilt should use Klipper's native mechanisms.

KAT should orchestrate these features, not replace them.

### Let the printer config own hardware behavior

KAT should not try to take over every hardware-specific detail.

For example:

- If a machine has `[homing_override]`, KAT should respect it.
- If a machine has a custom wipe routine, KAT should call it, not hardcode wiper coordinates.
- If a machine has Beacon, KAT can use Beacon-specific commands.
- If a machine does not have Beacon, KAT should fall back to standard Klipper behavior.

### Prefer helpers over duplicated math

Shared calculations should live in helpers:

- safe Z-hop
- named park positions
- end-print Z movement
- conditional homing
- park feedrate calculation

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

## About Hjort Creations

KAT is developed, sponsored, and maintained by Hjort Creations.

Hjort Creations is a Swedish additive manufacturing company working with large-format FDM, machine development, Klipper/Kalico workflows, and industrial 3D printing applications.

Read more:

```text
https://hjortcreations.se
```

---

## Credits and inspiration

KAT is built on top of the Klipper/Kalico ecosystem and is inspired by the work, ideas, documentation, and tooling from several open-source projects and communities.

Special thanks and inspiration from:

- Klipper
- Kalico
- Klipper-Adaptive-Meshing-Purging
- RatOS
- KIAUH
- Mainsail
- Moonraker
- Fluidd
- Beacon
- Voron
- The wider Klipper macro and 3D printing community

KAT is not affiliated with or officially endorsed by these projects unless explicitly stated. They are listed here because their work and ideas have helped shape how KAT is designed.

Project repository:

```text
https://github.com/HjortCreations/klipper_KAT
```

---

## Status

KAT is in early development.

The architecture is being defined and core files are being built step by step.

Expect changes while the project is still moving toward a stable first release.
