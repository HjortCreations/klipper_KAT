# KAT Macro Review Feedback

## Overall assessment

Your macro layout is solid and already easier to maintain than most Klipper bundles:

- **Clear layering:** `core_features.cfg` is a clean orchestrator and keeps includes readable.
- **Separation of concerns:** helper, workflow, and optional shell/resonance features are logically split.
- **Operator UX:** consistent `RESPOND` prefixes make console output understandable during failures.

---

## High-priority improvements (recommended first)

### 1) Add a strict macro contract header on workflow entrypoints
For `START_PRINT`, `END_PRINT`, `PAUSE`, `RESUME`, and `CANCEL_PRINT`, document:
- required params
- optional params + defaults
- state variables read/write
- assumptions (homed, heated, mesh loaded)

This prevents hidden coupling between files and makes slicer integration safer.

### 2) Standardize state-variable naming and lifecycle
You currently have good state use (e.g., `set_position_used`, `pause_lift_applied`), but add one convention:
- `*_requested` for inputs
- `*_applied` for clamped/actual values
- explicit reset point per print lifecycle (start/end/cancel)

This reduces stale-state bugs after interrupted jobs.

### 3) Centralize movement safety policy
`PARK_TOOLHEAD` and pause logic already clamp behavior, which is great. Formalize policy in one comment block reused across movement macros:
- homing precondition
- max travel edge margin
- Z-hop ceiling rule
- fallback behavior when preconditions fail

That keeps behavior consistent when new movement macros are added.

---

## Medium-priority improvements

### 4) Normalize console language
Use one term family consistently:
- `SKIP` for intentional no-op
- `FALLBACK` for alternate path
- `ABORT` for hard stop

Predictable wording helps remote operators quickly classify what happened.

### 5) Add a basic config QA script
A small script in `KAT/scripts/` can catch common issues before restart:
- missing include target
- duplicate `[gcode_macro ...]` names
- unterminated Jinja block markers
- accidental trailing quote/brace typos

Even a simple regex-based check gives high value.

### 6) Tighten advanced feature enablement docs
`advanced_features.cfg` docs are clear; add one explicit note:
- if advanced include is enabled but extension missing, expected Klipper startup error signature

This makes first-time troubleshooting faster.

---

## Low-priority polish

### 7) Add a quick command index
A compact table in README with macro purpose + common parameters would improve discoverability.

### 8) Align file naming wording
Use one naming pattern for "start print" references (`start_print.cfg`, `START_PRINT`, and docs text) to reduce cognitive overhead.

---

## Applied fix in this branch

- Confirmed/fixed the `SET_POSITION` `RESPOND` line typo by removing the stray trailing quote in `KAT/kat_helpers.cfg`.
