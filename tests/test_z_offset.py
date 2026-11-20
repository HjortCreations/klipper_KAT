"""Render the actual KAT templates and exercise their persistence contract.

No printer connection or physical operations. Run with Python + Jinja2.
"""
# Distributed under the GNU GPLv3 license; see ../LICENSE.
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import configparser
import json
import unittest
import jinja2

ROOT = Path(__file__).resolve().parents[1]


class MacroError(Exception):
    pass


def fail(message):
    raise MacroError(message)


class Harness:
    def __init__(self, path, enabled=True, storage=True):
        self.path = path
        self.enabled = enabled
        self.storage = storage
        self.limit = 1.0
        self.active = 0.0
        self.variables = json.loads(path.read_text()) if path.exists() else {}
        self.variables.setdefault('unrelated_setting', 'keep me')
        self.commands = []
        parser = configparser.RawConfigParser()
        parser.read(ROOT / 'z_offset.cfg', encoding='utf-8')
        env = jinja2.Environment(block_start_string='{%', block_end_string='%}',
                                 variable_start_string='{', variable_end_string='}')
        self.templates = {section.split(' ', 1)[1]: env.from_string(parser.get(section, 'gcode'))
                          for section in parser.sections()}

    def execute(self, name, **params):
        printer = {'gcode_macro KAT': SimpleNamespace(start_use_saved_z_offset=self.enabled,
                                                    z_offset_max_abs=self.limit),
                   'gcode_move': SimpleNamespace(homing_origin=SimpleNamespace(z=self.active))}
        if self.storage:
            printer['save_variables'] = SimpleNamespace(variables=self.variables)
        # Render to completion before executing any command, matching Klipper macro semantics.
        rendered = self.templates[name].render(printer=printer, params=params,
                                               action_raise_error=fail)
        for line in rendered.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            self.commands.append(line)
            if line.startswith('SAVE_VARIABLE '):
                args = dict(item.split('=', 1) for item in line.split()[1:])
                self.variables[args['VARIABLE']] = float(args['VALUE'])
                self.path.write_text(json.dumps(self.variables))
            elif line.startswith('SET_GCODE_OFFSET '):
                args = dict(item.split('=', 1) for item in line.split()[1:])
                assert args.get('MOVE') == '0', 'A test template attempted physical movement'
                assert 'Z_ADJUST' not in args, 'Saved compensation must be absolute'
                self.active = float(args['Z'])
            elif not line.startswith('RESPOND '):
                raise AssertionError('Unexpected emitted command: ' + line)
        return rendered


class PersistentOffsetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'variables.json'
        self.h = Harness(self.path)

    def test_save_current_is_immediate_persistent_and_does_not_move(self):
        self.h.active = .35
        self.h.execute('KAT_SAVE_Z_OFFSET')
        self.assertAlmostEqual(self.h.active, .35)
        restarted = Harness(self.path)
        self.assertEqual(restarted.variables['unrelated_setting'], 'keep me')
        restarted.execute('KAT_APPLY_Z_OFFSET')
        self.assertAlmostEqual(restarted.active, .35)
        self.assertFalse(any('SAVE_CONFIG' in c for c in self.h.commands))

    def test_two_calibration_cycles_do_not_accumulate(self):
        self.h.execute('KAT_SAVE_Z_OFFSET', Z='.32')
        for _ in range(2):
            self.h.active = .45  # previous print/babystep state
            self.h.execute('_KAT_PREPARE_Z_OFFSET')
            self.assertEqual(self.h.active, 0)
            # Contact regenerates the probe model; it does not touch KAT's file.
            self.h.execute('KAT_APPLY_Z_OFFSET')
            self.assertAlmostEqual(self.h.active, .32)
            self.h.execute('KAT_APPLY_Z_OFFSET')
            self.assertAlmostEqual(self.h.active, .32)

    def test_save_babystep_total_and_repeated_save(self):
        self.h.execute('KAT_SAVE_Z_OFFSET', Z='.32')
        self.h.execute('KAT_APPLY_Z_OFFSET')
        self.h.active += .03
        self.h.execute('KAT_SAVE_Z_OFFSET')
        self.h.execute('KAT_SAVE_Z_OFFSET')
        self.assertAlmostEqual(self.h.variables['kat_print_z_offset'], .35)

    def test_explicit_save_changes_storage_only_and_zero_clears(self):
        self.h.active = .35
        self.h.execute('KAT_SAVE_Z_OFFSET', Z='-.1')
        self.assertAlmostEqual(self.h.active, .35)
        self.h.execute('KAT_APPLY_Z_OFFSET')
        self.assertAlmostEqual(self.h.active, -.1)
        self.h.execute('KAT_SAVE_Z_OFFSET', Z='0')
        self.h.execute('KAT_APPLY_Z_OFFSET')
        self.assertEqual(self.h.active, 0)

    def test_invalid_explicit_values_have_no_side_effects(self):
        self.h.active = .35
        for value in ['', 'oops', 'nan', 'inf', '-inf', '1.01', '-1.01', '0.3\nG28']:
            with self.subTest(value=value), self.assertRaises(MacroError):
                self.h.execute('KAT_SAVE_Z_OFFSET', Z=value)
            self.assertFalse(self.path.exists())
            self.assertEqual(self.h.commands, [])
            self.assertEqual(self.h.active, .35)

    def test_corrupt_storage_blocks_start_and_apply_before_commands(self):
        for value in ['bad', float('nan'), float('inf'), 2]:
            for macro in ['_KAT_PREPARE_Z_OFFSET', 'KAT_APPLY_Z_OFFSET']:
                with self.subTest(value=value, macro=macro):
                    self.h.variables['kat_print_z_offset'] = value
                    with self.assertRaises(MacroError):
                        self.h.execute(macro)
                    self.assertEqual(self.h.commands, [])

    def test_missing_storage_and_opt_out(self):
        h = Harness(self.path, storage=False)
        for macro in ['KAT_SAVE_Z_OFFSET', '_KAT_PREPARE_Z_OFFSET', 'KAT_APPLY_Z_OFFSET']:
            with self.assertRaises(MacroError):
                h.execute(macro)
        h.enabled = False
        h.active = .42
        h.execute('_KAT_PREPARE_Z_OFFSET')
        h.execute('KAT_APPLY_Z_OFFSET')
        self.assertEqual(h.active, .42)

    def test_unknown_parameters_are_not_silently_ignored(self):
        for macro, params in [('KAT_SAVE_Z_OFFSET', {'OFFSET': '.32'}),
                              ('KAT_APPLY_Z_OFFSET', {'MOVE': '1'}),
                              ('KAT_SHOW_Z_OFFSET', {'Z': '.2'})]:
            with self.subTest(macro=macro), self.assertRaises(MacroError):
                self.h.execute(macro, **params)
        self.assertEqual(self.h.commands, [])

    def test_missing_value_is_zero_and_configured_limit_is_enforced(self):
        self.h.execute('KAT_APPLY_Z_OFFSET')
        self.assertEqual(self.h.active, 0)
        for limit in [0, -1, float('nan'), float('inf'), 5.1]:
            self.h.limit = limit
            with self.assertRaises(MacroError):
                self.h.execute('KAT_SAVE_Z_OFFSET', Z='.1')

    def test_default_is_opt_out_without_requiring_storage(self):
        variables = (ROOT / 'variables.cfg').read_text(encoding='utf-8')
        parser = configparser.RawConfigParser()
        parser.read_string(variables)
        default = parser.get('gcode_macro KAT', 'variable_start_use_saved_z_offset').split('#')[0].strip()
        self.assertEqual(default, 'False')
        h = Harness(self.path, enabled=False, storage=False)
        h.active = .42
        h.execute('_KAT_PREPARE_Z_OFFSET')
        h.execute('KAT_APPLY_Z_OFFSET')
        self.assertEqual(h.active, .42)
        self.assertFalse(any(c.startswith('SET_GCODE_OFFSET') for c in h.commands))
        self.assertFalse(self.path.exists())

    def test_show_reports_saved_and_active_without_changing_either(self):
        self.h.execute('KAT_SAVE_Z_OFFSET', Z='.2')
        self.h.active = .35
        before = self.path.read_bytes()
        rendered = self.h.execute('KAT_SHOW_Z_OFFSET')
        self.assertIn('Saved=0.2 mm; active total=0.35 mm', rendered)
        self.assertAlmostEqual(self.h.active, .35)
        self.assertEqual(self.path.read_bytes(), before)

    def test_limit_boundaries_and_invalid_limits_on_start_and_apply(self):
        for limit in [.001, 1.0, 5.0]:
            self.h.limit = limit
            for value in [-limit, limit]:
                self.h.execute('KAT_SAVE_Z_OFFSET', Z=str(value))
                self.h.execute('KAT_APPLY_Z_OFFSET')
                self.assertEqual(self.h.active, value)
        for limit in [0, -1, 'bad', float('nan'), float('inf'), 5.1]:
            self.h.limit = limit
            for macro in ['_KAT_PREPARE_Z_OFFSET', 'KAT_APPLY_Z_OFFSET']:
                self.h.commands.clear()
                with self.subTest(limit=limit, macro=macro), self.assertRaises(MacroError):
                    self.h.execute(macro)
                self.assertEqual(self.h.commands, [])

    def test_hooks_surround_calibration_and_precede_prime(self):
        start = (ROOT / 'start_print.cfg').read_text(encoding='utf-8')
        main = start.split('[gcode_macro KAT_LEVEL_GANTRY]', 1)[0]
        self.assertLess(main.index('_KAT_PREPARE_Z_OFFSET'), main.index('KAT_WAIT_BED_TEMPERATURE'))
        self.assertLess(main.index('_KAT_PREPARE_Z_OFFSET'), main.index('MAYBE_HOME'))
        self.assertLess(main.index('KAT_BED_MESH\n'), main.index('KAT_APPLY_Z_OFFSET\n'))
        self.assertLess(main.index('M109 S{extruder_temp}'), main.index('KAT_APPLY_Z_OFFSET\n'))
        self.assertLess(main.index('KAT_APPLY_Z_OFFSET\n'), main.index('KAT_PRIME PARK=0'))
        core = (ROOT / 'core_features.cfg').read_text(encoding='utf-8')
        self.assertIn('[include z_offset.cfg]', core)


if __name__ == '__main__':
    unittest.main(verbosity=2)
