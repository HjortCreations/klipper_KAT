"""Experimental extra tests; fake heaters/probes, no printer connection.

Geometry/math and actual command orchestration are exercised independently of
Klipper. The fake does not certify real motion, Beacon accuracy or surface safety.
"""
# Distributed under GNU GPLv3; see ../LICENSE.
import ast
import importlib.util
import shlex
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from test_z_offset import Harness

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'kat_beacon_temperature', ROOT / 'experimental/beacon_temperature/kat_beacon_temperature.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Error(Exception):
    pass


class Status:
    def __init__(self, **values):
        self.values = values

    def get_status(self, eventtime):
        return self.values


class Command:
    def __init__(self, **params):
        self.params = params
        self.messages = []

    def get_command_parameters(self):
        return self.params

    def get(self, key, default=None):
        return self.params.get(key, default)

    def get_int(self, key, default, minval, maxval):
        value = int(self.get(key, default))
        if not minval <= value <= maxval:
            raise Error('Invalid integer')
        return value

    def error(self, message):
        return Error(message)

    def respond_info(self, message):
        self.messages.append(message)


class Reactor:
    now = 0.

    def monotonic(self):
        return self.now

    def pause(self, when):
        self.now = when


class Heater:
    target = 0.
    temperature = 25.
    frozen = False

    def get_temp(self, eventtime):
        return (self.temperature if self.frozen else self.target, self.target)


class Toolhead(Status):
    def get_last_move_time(self):
        return 0.

    def get_extruder(self):
        return SimpleNamespace(get_name=lambda: 'extruder')

    def get_position(self):
        return [100., 100., 10., 0.]


class Gcode:
    def __init__(self, printer):
        self.p = printer
        self.commands = []
        self.registered = {}
        self.probes = iter([0., 0., .070, .003, .074])
        self.fail_probe = False
        self.fail_save = False

    def register_command(self, name, handler, desc):
        self.registered[name] = handler

    def run_script_from_command(self, text):
        for line in text.splitlines():
            self.commands.append(line)
            if line.startswith('SET_HEATER_TEMPERATURE'):
                self.p.heater.target = float(line.split('TARGET=')[1])
            elif line.startswith('PROBE '):
                if self.fail_probe:
                    raise Error('Injected probe failure')
                self.p.objects['beacon'].values.update(
                    last_z_result=next(self.probes), last_probe_result='ok')
            elif line.startswith('SAVE_VARIABLE '):
                if self.fail_save:
                    raise Error('Injected storage failure')
                args = dict(token.split('=', 1) for token in shlex.split(line)[1:])
                self.p.variables[args['VARIABLE']] = ast.literal_eval(args['VALUE'])


class Printer:
    def __init__(self):
        self.reactor = Reactor()
        self.heater = Heater()
        self.variables = {'unrelated': 'keep', 'kat_print_z_offset': .35}
        self.settings = {
            'beacon': {'x_offset': 0., 'y_offset': 20., 'contact_max_hotend_temperature': 275.},
            'bed_mesh': {'mesh_min': [5., 5.], 'mesh_max': [595., 595.]},
            'extruder': {'max_temp': 300.}}
        self.objects = {
            'beacon': Status(last_probe_result='ok', last_z_result=0.),
            'configfile': Status(settings=self.settings),
            'save_variables': Status(variables=self.variables),
            'gcode_macro KAT': Status(start_preheat_temp=150., start_use_saved_z_offset=True,
                                      z_offset_max_abs=1.),
            'print_stats': Status(state='standby'),
            'toolhead': Toolhead(axis_minimum=[0., 0., 0.],
                                 axis_maximum=[600., 600., 1200.], homed_axes='xyz'),
            'extruder': SimpleNamespace(get_heater=lambda: self.heater),
            'heaters': SimpleNamespace(set_temperature=self.set_temperature)}
        self.gcode = Gcode(self)
        self.objects['gcode'] = self.gcode

    def set_temperature(self, heater, temperature, wait):
        heater.target = temperature

    def get_reactor(self):
        return self.reactor

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)

    def is_shutdown(self):
        return False


class Config:
    def __init__(self, printer, **values):
        self.printer, self.values = printer, values

    def get_printer(self):
        return self.printer

    def get(self, key, default=None):
        return self.values.get(key, default)

    def getfloat(self, key, default, **limits):
        return float(self.get(key, default))

    def getboolean(self, key, default):
        return bool(self.get(key, default))

    def error(self, message):
        return Error(message)


class GeometryTests(unittest.TestCase):
    def test_rectangular_sizes_negative_origins_and_both_offset_signs(self):
        for size in (180., 300., 603.):
            for origin in (-30., 0., 10.):
                for offset in ((0., 17.71), (-25., -20.), (25., 20.)):
                    with self.subTest(size=size, origin=origin, offset=offset):
                        low, high = [origin, origin], [size, size]
                        p = mod.edge_point(low, high, offset, 10., (low, high))
                        self.assertLess(p[0], (origin + size) / 2.)
                        self.assertLess(p[1], (origin + size) / 2.)
                        for x, y in (p, (p[0] + offset[0], p[1] + offset[1])):
                            self.assertTrue(origin + 10. <= x <= size - 10.)
                            self.assertTrue(origin + 10. <= y <= size - 10.)

    def test_no_axis_only_guess_or_infeasible_surface(self):
        with self.assertRaises(ValueError):
            mod.edge_point([0, 0], [300, 300], [0, 20], 10)
        with self.assertRaises(ValueError):
            mod.edge_point([0, 0], [300, 300], [0, 281], 10, ([0, 0], [300, 300]))

    def test_circular_point_keeps_nozzle_and_beacon_inside(self):
        for offset in ((0, 20), (-20, -15)):
            p = mod.edge_point([-150, -150], [150, 150], offset, 10,
                               circle=([0, 0], 150))
            self.assertLess(p[0], 0)
            self.assertLess(p[1], 0)
            self.assertLessEqual(mod.math.hypot(*p), 140.)
            self.assertLessEqual(mod.math.hypot(p[0] + offset[0], p[1] + offset[1]), 140.)

    def test_explicit_point_validated_without_clamping_to_center(self):
        args = ([0, 0], [300, 300], [0, 20], 10)
        self.assertEqual(mod.edge_point(*args, bounds=([0, 0], [300, 300]),
                                       requested='25,30'), (25., 30.))
        for p in ('0,0', 'nan,20', '290,290'):
            with self.assertRaises(ValueError):
                mod.edge_point(*args, bounds=([0, 0], [300, 300]), requested=p)


class CalculationTests(unittest.TestCase):
    def test_two_cycles_fit_mm_per_100_degrees_and_general_interval(self):
        record = mod.calibration_record(150, 250, [0, .07, .003, .074], .015, .2, (15, 15))
        self.assertAlmostEqual(record['coefficient'], .0705)
        self.assertAlmostEqual(mod.thermal_offset(record, 150, 230, .2), .0564)
        other = mod.calibration_record(140, 290, [0, .105, 0, .105], .015, .2, (15, 15))
        self.assertAlmostEqual(other['coefficient'], .07)

    def test_bad_cycles_nonfinite_and_negative_expansion_rejected(self):
        for values in ([0, .1, 0, .15], [0, -.01, 0, -.01], [0, .3, 0, .3],
                       [0, float('nan'), 0, .1], [0, float('inf'), 0, .1], [0, .1]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                mod.calibration_record(150, 250, values, .015, .2, (15, 15))

    def test_no_extrapolation_or_corrupt_records(self):
        good = {'version': 1, 'coefficient': .07, 'low': 150, 'high': 250}
        for reference, target in ((149, 230), (150, 260), (float('nan'), 230)):
            with self.assertRaises(ValueError):
                mod.thermal_offset(good, reference, target, .2)
        for record in (None, {}, dict(good, version=99), dict(good, coefficient='bad'),
                       dict(good, coefficient=float('inf'))):
            with self.assertRaises(ValueError):
                mod.thermal_offset(record, 150, 230, .2)


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.p = Printer()
        self.m = mod.BeaconTemperature(Config(self.p, enabled=True, settle_time=5.))

    def test_preview_emits_no_motion_heat_or_save(self):
        self.m.cmd_calibrate(Command())
        self.assertEqual(self.p.gcode.commands, [])
        self.assertEqual(self.p.heater.target, 0.)
        self.assertNotIn(mod.KEY, self.p.variables)

    def test_complete_calibration_moves_to_edge_before_heating_and_saves_once(self):
        self.m.cmd_calibrate(Command(RUN=1))
        commands = self.p.gcode.commands
        xy = commands.index('G0 X15.000000 Y15.000000 F6000')
        heat = next(i for i, c in enumerate(commands) if c.startswith('SET_HEATER_TEMPERATURE'))
        self.assertLess(xy, heat)
        self.assertFalse(any(c.startswith('G28') for c in commands))
        self.assertEqual(sum(c.startswith('SAVE_VARIABLE') for c in commands), 1)
        self.assertAlmostEqual(self.p.variables[mod.KEY]['coefficient'], .0705)
        self.assertEqual(self.p.variables['unrelated'], 'keep')
        self.assertEqual(self.p.variables['kat_print_z_offset'], .35)
        self.assertEqual(self.p.heater.target, 0.)
        self.assertFalse(self.m.running)
        self.assertTrue(commands[-1].endswith('MOVE=0'))

    def test_probe_failure_turns_off_heater_restores_modes_and_retains_old_record(self):
        self.p.variables[mod.KEY] = {'old': 'keep'}
        self.p.gcode.fail_probe = True
        with self.assertRaisesRegex(Error, 'probe failure'):
            self.m.cmd_calibrate(Command(RUN=1))
        self.assertEqual(self.p.variables[mod.KEY], {'old': 'keep'})
        self.assertEqual(self.p.heater.target, 0.)
        self.assertEqual(self.m.last_result, 'failed')
        self.assertFalse(self.m.running)
        self.assertTrue(self.p.gcode.commands[-1].startswith('RESTORE_GCODE_STATE'))

    def test_storage_failure_turns_off_heater_and_restores_state(self):
        self.p.gcode.fail_save = True
        self.m.applied, self.m.reference = .05, 150.
        with self.assertRaisesRegex(Error, 'storage failure'):
            self.m.cmd_calibrate(Command(RUN=1))
        self.assertEqual(self.p.heater.target, 0.)
        self.assertEqual(self.m.applied, .05)
        self.assertEqual(self.m.reference, 150.)
        self.assertNotIn(mod.KEY, self.p.variables)

    def test_temperature_timeout_turns_off_heater(self):
        self.p.heater.frozen = True
        self.m.timeout = 1.
        with self.assertRaisesRegex(Error, 'Timed out'):
            self.m.cmd_calibrate(Command(RUN=1))
        self.assertEqual(self.p.heater.target, 0.)
        self.assertNotIn(mod.KEY, self.p.variables)

    def test_unhomed_printing_paused_hot_bed_and_mesh_block_before_heat(self):
        mutations = [lambda: self.p.objects['toolhead'].values.update(homed_axes='xy'),
                     lambda: self.p.objects['print_stats'].values.update(state='printing'),
                     lambda: self.p.objects['print_stats'].values.update(state='paused'),
                     lambda: self.p.objects.update(heater_bed=Status(temperature=65., target=0.)),
                     lambda: self.p.objects.update(heater_bed=Status(temperature=25., target=60.)),
                     lambda: self.p.objects.update(bed_mesh=SimpleNamespace(get_mesh=lambda: object()))]
        for mutation in mutations:
            self.setUp()
            mutation()
            with self.assertRaises(Error):
                self.m.cmd_calibrate(Command(RUN=1))
            self.assertEqual(self.p.gcode.commands, [])

    def test_contact_temperature_cap_never_silently_raised(self):
        del self.p.settings['beacon']['contact_max_hotend_temperature']
        with self.assertRaisesRegex(Error, 'contact limit'):
            self.m.cmd_calibrate(Command(RUN=1))
        self.assertEqual(self.p.gcode.commands, [])

    def test_idle_timeout_is_restored_even_when_probe_fails(self):
        self.p.objects['idle_timeout'] = SimpleNamespace(idle_timeout=600.)
        self.p.gcode.fail_probe = True
        with self.assertRaises(Error):
            self.m.cmd_calibrate(Command(RUN=1))
        commands = self.p.gcode.commands
        self.assertIn('SET_IDLE_TIMEOUT TIMEOUT=3300.000', commands)
        self.assertIn('SET_IDLE_TIMEOUT TIMEOUT=600.000', commands)
        self.assertEqual(self.p.heater.target, 0.)

    def test_default_enabled_false_and_nonfinite_configuration_rejected(self):
        m = mod.BeaconTemperature(Config(self.p))
        self.assertFalse(m.enabled)
        for name in ('settle_time', 'temperature_timeout', 'cycle_tolerance', 'max_coefficient'):
            with self.subTest(name=name), self.assertRaises(Error):
                mod.BeaconTemperature(Config(self.p, **{name: float('nan')}))

    def test_delta_lowers_before_xy_at_edge_and_accepts_cold_bed(self):
        self.p.settings['printer'] = {'kinematics': 'delta'}
        self.p.objects['heater_bed'] = Status(temperature=25., target=0.)
        self.p.gcode.fail_probe = True
        with self.assertRaises(Error):
            self.m.cmd_calibrate(Command(RUN=1))
        commands = self.p.gcode.commands
        self.assertLess(commands.index('G0 Z5.000000 F300'),
                        commands.index('G0 X15.000000 Y15.000000 F6000'))

    def test_composition_is_idempotent_and_manual_part_saved_separately(self):
        self.p.variables[mod.KEY] = {'version': 1, 'coefficient': .07, 'low': 150., 'high': 250.}
        self.m.cmd_prepare(Command(TARGET=230))
        self.p.heater.target = 230.
        self.m.cmd_apply(Command())
        self.m.cmd_apply(Command())
        self.assertEqual(self.p.gcode.commands[-1], 'SET_GCODE_OFFSET Z=0.406000000 MOVE=0')
        with TemporaryDirectory() as directory:
            h = Harness(Path(directory) / 'state.json', thermal=SimpleNamespace(enabled=True, applied=self.m.applied))
            h.active = .416  # .35 user + .056 thermal + .01 new baby step
            h.execute('KAT_SAVE_Z_OFFSET')
            self.assertAlmostEqual(h.variables['kat_print_z_offset'], .36)
            h.execute('KAT_SAVE_Z_OFFSET', Z='.32')
            self.assertAlmostEqual(h.variables['kat_print_z_offset'], .32)
            h.execute('KAT_APPLY_Z_OFFSET')
            self.assertEqual(h.commands[-1], 'KAT_APPLY_NOZZLE_TEMP_OFFSET')

    def test_disabled_extra_needs_no_record_and_does_not_change_runtime(self):
        self.m.enabled = False
        self.m.applied = .01
        self.m.cmd_prepare(Command(TARGET=230))
        self.assertEqual(self.m.applied, .01)
        self.assertEqual(self.p.gcode.commands, [])

    def test_invalid_record_and_temperature_stop_prepare_before_reset(self):
        with self.assertRaises(Error):
            self.m.cmd_prepare(Command(TARGET=230))
        self.p.variables[mod.KEY] = {'version': 1, 'coefficient': .07, 'low': 150., 'high': 250.}
        with self.assertRaises(Error):
            self.m.cmd_prepare(Command(TARGET=280))
        self.assertEqual(self.p.gcode.commands, [])

    def test_unknown_parameters_multitool_and_apply_without_prepare_rejected(self):
        with self.assertRaisesRegex(Error, 'Unknown'):
            self.m.cmd_calibrate(Command(HEAT=1))
        with self.assertRaisesRegex(Error, 'PREPARE'):
            self.m.cmd_apply(Command())
        self.p.settings['extruder1'] = {}
        with self.assertRaisesRegex(Error, 'single toolhead'):
            self.m.cmd_calibrate(Command(RUN=1))
        self.assertEqual(self.p.gcode.commands, [])

    def test_non_native_probe_ownership_rejected(self):
        self.p.settings['beacon']['register_as_probe'] = False
        with self.assertRaisesRegex(Error, 'PROBE ownership'):
            self.m.cmd_calibrate(Command(RUN=1))
        self.assertEqual(self.p.gcode.commands, [])

    def test_start_hook_precedes_heating_and_opt_in_is_not_in_core(self):
        start = (ROOT / 'start_print.cfg').read_text(encoding='utf-8')
        self.assertLess(start.index('KAT_PREPARE_NOZZLE_TEMP_OFFSET'),
                        start.index('KAT_WAIT_BED_TEMPERATURE'))
        self.assertNotIn('beacon_temperature', (ROOT / 'core_features.cfg').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
