# Persistent print Z offset

This opt-in KAT feature preserves a user print-height correction independently of a probe model. It is intended for workflows that recreate a model/reference with Beacon Contact at every print start, and can also be used with other compatible KAT probing workflows. It is not a replacement for probe calibration or a temperature-compensation model.

The implementation lives in `z_offset.cfg`, loaded by `core_features.cfg`. It uses ordinary Klipper/Kalico macros and `save_variables`; it does not require RatOS modules, replace Beacon commands or hardcode a machine name or offset.

## Enable

KAT's default is **disabled**, preserving existing installations. In the printer configuration, after the KAT includes, configure persistence and opt in:

```ini
[save_variables]
filename: ~/printer_data/config/kat-variables.ini

[gcode_macro KAT]
variable_start_use_saved_z_offset: True
```

If the machine already has `[save_variables]`, reuse that section and its existing file; do not add a competing filename. KAT writes only the key `kat_print_z_offset` and preserves other saved variables. Keep the state file outside the KAT checkout so toolkit updates cannot replace machine data. It is runtime state, not an included hardware CFG.

`variable_z_offset_max_abs` defaults to 1.0 mm. It sets the accepted positive/negative compensation range; configurable limits are 0.001..5.0 mm. Invalid, nonnumeric, NaN/infinite or out-of-range saved values stop the preparation helper before heating/homing. Increasing the range is an explicit machine configuration decision.

## Commands

| Command | Behaviour |
|---|---|
| `KAT_SAVE_Z_OFFSET` | Save the **current total runtime Z offset** as an absolute value |
| `KAT_SAVE_Z_OFFSET Z=0.32` | Save exactly +0.32 mm for future application; does not add 0.32 to a previous value |
| `KAT_SAVE_Z_OFFSET Z=0` | Save zero compensation |
| `KAT_SHOW_Z_OFFSET` | Show saved value, active total and whether print-start integration is enabled |
| `KAT_APPLY_Z_OFFSET` | Apply the saved absolute value with `MOVE=0`; requires integration enabled |

Saving writes the variables file immediately. It does **not** issue `SAVE_CONFIG`, restart the host, move the axes, or change the active offset. Therefore an already applied first-layer baby-step can be saved while printing. After saving an explicit different value, the active value remains unchanged until `KAT_APPLY_Z_OFFSET` or the next integrated print start. Applying affects subsequent absolute Z moves; `MOVE=0` means no immediate move, not that it cannot influence later movement.

Unexpected parameters are rejected. For example, use `Z=0.32`, not `OFFSET=0.32`; apply/show take no parameters.

Positive values increase nozzle-to-bed clearance on subsequent print moves. Do not copy a value from another machine or add the same correction to both the probe model and KAT.

The unqualified save captures the total runtime offset. This feature does not separate independent slicer/material/thermal/named offsets. If other systems contribute to that total, account for them explicitly before saving. It is deliberately not a full RatOS named-offset replacement.

## Print lifecycle

1. `START_PRINT` calls `_KAT_PREPARE_Z_OFFSET` before heating. It validates storage/value and sets runtime Z offset to zero using `MOVE=0`.
2. Existing homing, leveling, Contact/model calibration and mesh steps run normally.
3. After the final nozzle-temperature wait, before priming, `KAT_APPLY_Z_OFFSET` reads the persisted value and assigns it absolutely.
4. Normal printing and existing KAT pause/resume/end behaviour continue.

The helpers are separate macros so the saved state is read when the helper executes, not captured prematurely while the outer `START_PRINT` template is expanded. Applying and saving twice is idempotent. A new Contact model never writes KAT's saved key.

This integration covers KAT's standard `START_PRINT`. A custom start routine must call the preparation/apply helpers around its own calibration. A manual Contact/homing command outside this flow is not automatically intercepted; apply the saved compensation afterward if appropriate. On a fresh host start the value is available in storage, and the normal print workflow applies it after calibration.

## First-layer workflow

1. Start a supervised first-layer test through KAT.
2. Adjust the UI Z offset until the layer is correct.
3. Run `KAT_SAVE_Z_OFFSET` once. `KAT_SHOW_Z_OFFSET` reports what was saved.
4. Start a second supervised print and confirm the value is reapplied after Contact.

Use these KAT commands to save print-height compensation. The existing Beacon `Z_OFFSET_APPLY_PROBE` / UI probe-save action remains a model-offset operation and is **not** redirected to KAT's store.

## Validation and compatibility

The Herkules trial exercised template rendering, invalid inputs, missing storage, opt-out behaviour, persistent saving, repeated saving/application and lifecycle hook ordering. Native no-motion checks also verified saving and restoration across a Kalico restart. A subsequent operator-started print showed Contact followed by saved-offset restoration before printing, and the operator confirmed that the first-layer height looked correct. That is a machine-trial result; simulated reset/reapply checks do not certify other machines' nozzle height or calibration accuracy.

The feature is included in shared KAT as an opt-in workflow. Existing installations remain disabled until explicitly configured. Beacon Contact has been exercised on Herkules; other probe workflows require their own supervised first-layer verification. Custom start routines must use the documented helper ordering. The implementation and accompanying tests use KAT's GNU GPLv3 license.

Update and restart Klipper/Kalico only when the printer is idle. A macro hot reload during the CB1 trial coincided with an MCU timing shutdown; use a normal idle restart rather than `RELOAD_GCODE_MACROS` for deployment. No printer is updated automatically by this repository change.

To disable integration, set `variable_start_use_saved_z_offset: False` and restart while idle. Disabling does not immediately clear an already active runtime offset. Keep the state file for recovery; the next host restart resets the runtime state, and disabled KAT will not reapply the saved value.

To run the isolated tests from the KAT checkout with Python/Jinja2 available:

```bash
python -m pip install -r tests/requirements.txt
python tests/test_z_offset.py
```

The 13 tests render this checkout's actual templates with a simulated printer and temporary storage. They cover persistence/reconstruction, repeated saving/application, invalid inputs and limits, opt-out without storage, status reporting and lifecycle hook ordering. They do not connect to a printer. GitHub Actions runs the suite on pushes and pull requests. On Herkules the installed Kalico Python environment already supplies Jinja2, so no runtime packages were installed for the trial.
