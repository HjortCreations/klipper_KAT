# Experimental Beacon nozzle temperature calibration

**Experimental. No physical temperature calibration has been performed for this
implementation. Test on your own supervised machine before relying on it.**

This optional Klipper/Kalico extra measures hotend thermal expansion using Beacon
Contact, then adds temperature compensation to KAT's saved user Z correction.
Core KAT does not install or enable the extra. Updating KAT alone changes no
temperature-calibration workflow on existing printers.

## What it measures

The measurement sequence is inspired by [RatOS's Beacon implementation](https://github.com/Rat-OS/RatOS-configurator/blob/v2.1.x/configuration/z-probe/beacon.cfg)
and [hotend expansion documentation](https://os.ratrig.com/docs/configuration/beacon/#3-hotend-expansion-calibration):

1. Use an already homed/leveled printer; this routine never runs `G28` or QGL.
2. Save G-code modes and offsets. Move to a verified edge point before heating.
3. Stabilize at the low temperature and take ten settling Contact samples.
4. Measure **150 → 250 → 150 → 250 °C** by default. Each result is the median of
   five Contact samples, using 3 mm/s probing, 3 mm retract, 0.005 mm sample
   tolerance and up to ten tolerance retries, following RatOS's sampling approach.
5. Calculate each cycle's expansion in **mm per 100 °C**. Reject negative,
   excessive or inconsistent coefficients. Average the two accepted cycles.
6. Save one complete record through native `save_variables`, retaining unrelated
   variables. Turn off the nozzle and restore modes/offsets with `MOVE=0`.

There is a bounded wait for a continuously stable ±1 °C band at each temperature
(30 seconds by default). The coefficient is a linear model, not an arbitrary
table of unrelated offsets. A different calibration interval can be requested.
No compensation is extrapolated outside that interval.

The corner position reduces center-of-sheet deflection as a measurement source;
it does not eliminate mechanical drift, changing chamber temperature, plate
deformation or surface indentation. Agreement between cycles is a repeatability
check, not proof of absolute accuracy.

## Edge selection across machines

For a rectangular bed, KAT intersects nozzle XY travel with a conservative usable
surface, including the Beacon X/Y offset. Both the nozzle and coil must remain
inside the surface with a **10 mm margin** by default. It selects the lowest
valid X and Y, near the coordinate-minimum corner, independently of endstop
direction. That corner is not necessarily the operator's physical front-left.

The surface comes from explicit `bed_min`/`bed_max`, otherwise from the rectangular
`[bed_mesh] mesh_min`/`mesh_max`. Mesh bounds are sensor coordinates; treating
them as a usable surface for BOTH nozzle and coil is intentionally conservative.
It can place the point farther inward than the physical edge. KAT does not guess
the bed surface from axis travel, which may include off-bed overtravel.

For a circular `[bed_mesh]`, KAT uses `mesh_radius` and `mesh_origin`, erodes the
radius by the margin and Beacon offset length, and chooses the -X/-Y diagonal
edge. On delta kinematics it first lowers to the clearance at the current XY,
avoiding a sideways move at the restricted top of travel. This geometry has
offline coverage only; delta motion has not been physically validated.

`calibration_point: X,Y` overrides the automatic point but must pass the same
surface/nozzle/coil checks. No fallback silently moves the measurement to center.
**Bounds checks cannot detect clips, purge buckets, damaged coating, holes or
other obstructions. Verify the preview and the physical point on each machine.**

## Installation

This uses a small native extra because a sequence of G-code macros cannot provide
reliable exception cleanup around failed probing/heating/storage. The extra
turns the nozzle off in `finally` and attempts state restoration without movement.
Its temperature waits yield to Klipper's reactor; it performs no heavy analysis.

From the printer host:

```bash
cd ~/printer_data/config/KAT
sh experimental/beacon_temperature/install.sh ~/klipper
```

Pass the actual firmware source path if it differs, for example `~/kalico`.
The installer creates a symlink in `klippy/extras`; it refuses to replace an
unrelated file or link and does not restart services or operate the printer.
Installing requires a normal idle host restart; macro hot reload is insufficient.

Add this to your own `printer.cfg`, outside the update-managed KAT files:

```ini
[save_variables]
filename: ~/printer_data/config/kat-variables.ini

[kat_beacon_temperature]
enabled: False
# Defaults: low_temp 150, high_temp 250, edge_margin 10, settle_time 30.
# Optional verified usable surface if mesh bounds are absent or too restrictive:
# bed_min: 0, 0
# bed_max: 300, 300
# Optional nozzle-coordinate override:
# calibration_point: 25, 25

[gcode_macro KAT]
variable_start_use_saved_z_offset: True
```

Reuse an existing `[save_variables]` section/file and existing KAT override section.
Keep runtime state outside the KAT checkout. `enabled: False` allows calibration
and inspection but does not apply thermal compensation during printing.

Requirements: a single-toolhead printer with working Beacon Contact, native
`PROBE` owned by Beacon, standard XYZ motion and KAT core. IDEX, multiple
extruders, tool changers, RatOS named-offset integration and other probe brands
are outside this first experiment. Avoid combining it with another thermal
Z-compensation system.

## Supervised calibration

1. Unload filament and thoroughly clean the nozzle. Use a surface that tolerates
   contact at the high temperature, such as a verified bare-metal region.
   **Do not perform this hot calibration on smooth PEI.** See
   [Beacon Contact surface guidance](https://docs.beacon3d.com/contact/).
2. Configure `[beacon] contact_max_hotend_temperature` explicitly for the suitable
   surface, e.g. 275 for the default 250 °C experiment. KAT respects this limit
   with 2 °C headroom and the heater maximum with 5 °C headroom; it never raises
   either limit. A nozzle point near an edge must still leave the coil over metal.
3. Turn the bed off and let it cool below 50 °C (default). Keep chamber conditions
   stable. Home/level using your ordinary low-temperature workflow, then run
   `BED_MESH_CLEAR` and `SET_SKEW CLEAR=1` if those features are active.
4. Preview without motion or heating:

   ```gcode
   KAT_CALIBRATE_NOZZLE_TEMP_OFFSET
   ```

5. Check the reported XY point against the physical sheet and clip positions.
   Clear the area, supervise the printer, and explicitly run:

   ```gcode
   KAT_CALIBRATE_NOZZLE_TEMP_OFFSET RUN=1
   KAT_SHOW_NOZZLE_TEMP_OFFSET
   ```

For a different supported print range, use the same parameters for preview/run:

```gcode
KAT_CALIBRATE_NOZZLE_TEMP_OFFSET LOW_TEMP=150 HIGH_TEMP=290
KAT_CALIBRATE_NOZZLE_TEMP_OFFSET RUN=1 LOW_TEMP=150 HIGH_TEMP=290
```

This example requires correspondingly suitable hardware, surface and temperature
limits. The interval must span at least 30 °C. The calibration makes no automatic
return to center, performs no extrusion, and leaves the hotend target at zero.
It preserves the existing bed/chamber targets; an active/heated bed blocks the
run. An active print, paused print, active mesh or skew also blocks it.

On an exception after the run begins, the nozzle is turned off in cleanup and
G-code state restoration is attempted without movement. A shutdown/disconnect can
prevent restoration; firmware shutdown remains authoritative. Stop the machine
with its normal emergency stop if necessary, then rehome before a later test.
The previous calibration is not replaced until a complete accepted result exists.
Persistence uses Klipper's native variables-file writer; one record prevents a
mixed coefficient/metadata update but does not promise filesystem atomicity
against power loss or storage failure. Keep a backup of the variables file.

## Enable for first-layer trials

After reviewing the result, set `enabled: True` in `[kat_beacon_temperature]` and
restart while idle. With standard KAT `START_PRINT`:

- Before heating/homing, validate the record and selected print temperature.
- Use KAT's `start_preheat_temp` as the Contact reference temperature.
- Clear the previous runtime correction before calibration and meshing.
- After Contact, mesh and final heating, apply the absolute sum:

  ```text
  thermal = coefficient × (print target - Contact reference) / 100
  total Z correction = saved user correction + thermal
  ```

Both temperatures must lie inside the measured interval. For example, a measured
0.07 mm/100 °C gives +0.056 mm from 150 to 230 °C. No coefficient or manual offset
from Herkules is shipped as a default. There is no change to Beacon's probe model.

`KAT_SAVE_Z_OFFSET` without `Z=` now subtracts the extra's tracked applied thermal
contribution before saving the user correction. Explicit `Z=` remains an absolute
user value. Repeated application does not stack either contribution.

**Re-tune the manual correction when first enabling thermal compensation.** An
old manually tuned value may already include hotend expansion; blindly retaining
it and adding thermal compensation can count that expansion twice. Save a suitable
starting user value, then supervise and adjust the next first layer. The code
does not guess how an older correction was obtained.

The compensation uses the target at print-start application. It does not intercept
later slicer temperature changes or continuously move Z as actual temperature
fluctuates. `KAT_APPLY_NOZZLE_TEMP_OFFSET` can explicitly recompute the contribution
after a prepared start; it uses `MOVE=0`, affecting later moves only. A custom
start must call `KAT_PREPARE_NOZZLE_TEMP_OFFSET TARGET=...` before calibration and
`KAT_APPLY_Z_OFFSET` after calibration/heating. The reference must match the actual
Contact probing temperature. Do not add another hot Contact reference afterward
without preparing the contributions again.

## Configuration reference

| Setting | Default | Purpose |
|---|---|---|
| `enabled` | `False` | Enable print-start compensation; calibration is still explicit |
| `low_temp`, `high_temp` | `150`, `250` | Measurement interval, optionally overridden per calibration |
| `edge_margin` | `10` mm | Minimum usable-surface inset for both nozzle and coil |
| `bed_min`, `bed_max` | unset | Optional explicit rectangular usable surface |
| `calibration_point` | automatic | Optional validated nozzle XY point |
| `clearance` | `5` mm | Z height for probing/edge travel; verify clip clearance |
| `settle_time` | `30` seconds | Continuous ±1 °C stability before measurements |
| `temperature_timeout` | `600` seconds | Maximum wait for each stable temperature |
| `cycle_tolerance` | `0.015` mm/100 °C | Maximum difference between cycle coefficients |
| `max_coefficient` | `0.20` mm/100 °C | Maximum accepted coefficient; no negative values |
| `max_bed_temp` | `50` °C | Highest actual bed temperature allowed for the experiment |

The combined thermal/user offset must respect KAT's existing `z_offset_max_abs`.
An enabled experiment with absent/corrupt data or an out-of-range print temperature
stops the standard start before heating. Runtime status is exposed as
`printer.kat_beacon_temperature`; `applied` is only the extra's thermal component.

State is one versioned `kat_nozzle_temp_calibration` record in the native variables
file, containing the coefficient, interval, both cycle coefficients, raw median
results and point. Back up this file. Recalibrate after a nozzle/hotend change;
the software cannot identify a physically swapped nozzle.

## Disable or remove

Set `enabled: False` and restart while idle to return to fixed user compensation.
Retune any manual value previously saved with thermal compensation enabled.
For full removal, remove the config section and **only the module symlink created
by the installer**, then restart while idle. Keep the saved record for recovery.

## Validation boundary

Automated tests cover rectangular/circular edge geometry, both probe-offset signs,
negative origins, different machine sizes, coefficient fitting, corrupt data,
cycle disagreement, preview/no-side-effects, command ordering, heater cleanup on
probe/storage/temperature failure, print-start composition and manual-save
separation. They use simulated hardware, not a connected printer. The physical
home-machine trials requested by the operator remain outstanding.

```bash
python -m pip install -r tests/requirements.txt
python -m unittest discover -s tests -v
```

See [the validation record](VALIDATION.md) for completed offline checks and the
remaining physical-test boundary.

The implementation is original KAT code under GNU GPLv3. RatOS supplies the
measurement approach; Beacon supplies the actual Contact probing implementation.
