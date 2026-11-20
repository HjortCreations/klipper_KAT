# Experimental KAT Beacon hotend expansion calibration.
# Copyright (C) 2026 Hjort Creations
# Distributed under the GNU GPLv3 license; see ../../LICENSE.
"""Optional Klipper/Kalico extra; never installed or enabled by KAT core.

RatOS inspires the two low/high cycles and median Contact measurements.
KAT uses an edge location, complete calibration records and a separate user offset.
"""
import math


KEY = 'kat_nozzle_temp_calibration'


def finite(value, name, low=-1.e9, high=1.e9):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError('%s must be a finite number' % name)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError('%s must be within %g..%g' % (name, low, high))
    return result


def pair(value, name):
    if isinstance(value, str):
        value = value.split(',')
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('%s must contain X,Y' % name)
    return tuple(finite(v, name) for v in value)


def edge_point(axis_min, axis_max, offset, margin, bounds=None,
               circle=None, requested=None):
    """Keep BOTH nozzle and coil inside a known surface and nozzle travel.

    Mesh bounds are a conservative usable surface, not inferred bed dimensions.
    Circular beds use a conservative offset-eroded radius toward the -X/-Y edge.
    """
    amin, amax = pair(axis_min, 'axis_min'), pair(axis_max, 'axis_max')
    ox, oy = pair(offset, 'Beacon offset')
    margin = finite(margin, 'edge_margin', 1., 100.)
    if any(a >= b for a, b in zip(amin, amax)):
        raise ValueError('Invalid XY travel limits')
    if bounds is not None:
        bmin, bmax = pair(bounds[0], 'bed_min'), pair(bounds[1], 'bed_max')
        lo = tuple(max(a, b + margin, b + margin - o)
                   for a, b, o in zip(amin, bmin, (ox, oy)))
        hi = tuple(min(a, b - margin, b - margin - o)
                   for a, b, o in zip(amax, bmax, (ox, oy)))
        if any(a > b for a, b in zip(lo, hi)):
            raise ValueError('No common nozzle/Beacon area with this edge margin')
        point = pair(requested, 'point') if requested is not None else lo
        if any(not a <= p <= b for p, a, b in zip(point, lo, hi)):
            raise ValueError('Requested point is outside nozzle/Beacon safe bounds')
    elif circle is not None:
        center, radius = pair(circle[0], 'mesh_origin'), finite(circle[1], 'mesh_radius', 1.)
        safe_radius = radius - margin - math.hypot(ox, oy)
        if safe_radius <= 0:
            raise ValueError('Circular bed too small for margin and Beacon offset')
        if requested is None:
            point = tuple(max(a, min(b, c - safe_radius / math.sqrt(2.)))
                          for a, b, c in zip(amin, amax, center))
        else:
            point = pair(requested, 'point')
        coil = (point[0] + ox, point[1] + oy)
        if (any(not a <= p <= b for p, a, b in zip(point, amin, amax))
                or any(math.hypot(p[0] - center[0], p[1] - center[1])
                       > radius - margin + 1.e-8 for p in (point, coil))):
            raise ValueError('Requested point is outside circular nozzle/Beacon area')
    else:
        raise ValueError('Define bed_min/bed_max or a rectangular/circular [bed_mesh]; '
                         'axis travel alone does not identify a safe bed surface')
    return point


def calibration_record(low, high, readings, agreement, max_coefficient, point):
    low, high = finite(low, 'low', 50., 350.), finite(high, 'high', 50., 350.)
    if high - low < 30.:
        raise ValueError('Calibration temperatures must differ by at least 30 C')
    values = [finite(v, 'probe result') for v in readings]
    if len(values) != 4:
        raise ValueError('Two complete low/high measurement cycles are required')
    slopes = [(values[i+1] - values[i]) * 100. / (high - low) for i in (0, 2)]
    if any(not 0. <= v <= max_coefficient for v in slopes):
        raise ValueError('Expansion coefficient outside 0..%g mm/100 C; '
                         'inspect nozzle, mounting and measurements' % max_coefficient)
    if abs(slopes[1] - slopes[0]) > agreement:
        raise ValueError('Temperature cycles disagree; old calibration was retained')
    return {'version': 1, 'coefficient': sum(slopes) / 2., 'low': low, 'high': high,
            'cycles': slopes, 'readings': values, 'point': list(point)}


def thermal_offset(record, reference, target, max_coefficient):
    if not isinstance(record, dict) or record.get('version') != 1:
        raise ValueError('Run KAT_CALIBRATE_NOZZLE_TEMP_OFFSET before enabling compensation')
    coefficient = finite(record.get('coefficient'), 'saved coefficient', 0., max_coefficient)
    low, high = finite(record.get('low'), 'saved low'), finite(record.get('high'), 'saved high')
    if high - low < 30.:
        raise ValueError('Invalid saved calibration interval')
    reference = finite(reference, 'Contact reference temperature', low, high)
    target = finite(target, 'print temperature', low, high)
    return coefficient * (target - reference) / 100.


class BeaconTemperature:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        self.enabled = config.getboolean('enabled', False)
        self.margin = config.getfloat('edge_margin', 10., minval=1., maxval=100.)
        bmin, bmax = config.get('bed_min', None), config.get('bed_max', None)
        if (bmin is None) != (bmax is None):
            raise config.error('Specify both bed_min and bed_max')
        self.bounds = (bmin, bmax) if bmin is not None else None
        self.point = config.get('calibration_point', None)
        self.low = config.getfloat('low_temp', 150., minval=50., maxval=350.)
        self.high = config.getfloat('high_temp', 250., minval=50., maxval=350.)
        self.settle = config.getfloat('settle_time', 30., minval=5., maxval=300.)
        self.timeout = config.getfloat('temperature_timeout', 600., minval=30., maxval=1800.)
        self.clearance = config.getfloat('clearance', 5., minval=3., maxval=20.)
        self.agreement = config.getfloat('cycle_tolerance', .015, above=0., maxval=.05)
        self.max_coefficient = config.getfloat('max_coefficient', .20, above=0., maxval=.5)
        self.max_bed_temp = config.getfloat('max_bed_temp', 50., minval=20., maxval=80.)
        # Upstream Klipper float bounds alone do not reject NaN on every version.
        try:
            for name, lower, upper in [('margin', 1., 100.), ('low', 50., 350.),
                                       ('high', 50., 350.), ('settle', 5., 300.),
                                       ('timeout', 30., 1800.), ('clearance', 3., 20.),
                                       ('agreement', .000001, .05),
                                       ('max_coefficient', .000001, .5),
                                       ('max_bed_temp', 20., 80.)]:
                finite(getattr(self, name), name, lower, upper)
        except ValueError as e:
            raise config.error(str(e))
        self.applied = 0.
        self.reference = None
        self.running = False
        self.last_result = None
        for name, method, desc in [
            ('KAT_CALIBRATE_NOZZLE_TEMP_OFFSET', self.cmd_calibrate,
             'EXPERIMENTAL: preview edge calibration; RUN=1 heats and probes'),
            ('KAT_SHOW_NOZZLE_TEMP_OFFSET', self.cmd_show,
             'Show experimental hotend expansion calibration and runtime contribution'),
            ('KAT_PREPARE_NOZZLE_TEMP_OFFSET', self.cmd_prepare,
             'Validate experimental temperature compensation before START_PRINT heat'),
            ('KAT_APPLY_NOZZLE_TEMP_OFFSET', self.cmd_apply,
             'Compose saved user and experimental thermal Z offsets without moving')]:
            self.gcode.register_command(name, method, desc=desc)

    def _object(self, name):
        obj = self.printer.lookup_object(name, None)
        if obj is None:
            raise ValueError('Experimental temperature calibration requires [%s]' % name)
        return obj

    def _settings(self):
        return self._object('configfile').get_status(self.reactor.monotonic())['settings']

    def _variables(self):
        return self._object('save_variables').get_status(self.reactor.monotonic())['variables']

    def _kat(self):
        return self._object('gcode_macro KAT').get_status(self.reactor.monotonic())

    def _single_tool(self):
        self._object('beacon')
        settings = self._settings()
        if (not settings.get('beacon', {}).get('register_as_probe', True)
                or 'gcode_macro PROBE' in settings):
            raise ValueError('Experimental calibration requires native Beacon PROBE ownership')
        if ('dual_carriage' in settings or any(
                n.startswith('extruder') and n[8:].isdigit() for n in settings)):
            raise ValueError('Experimental version supports a single toolhead only')
        th = self._object('toolhead')
        if th.get_extruder().get_name() != 'extruder':
            raise ValueError('Active toolhead must be extruder')
        return th

    def _point(self):
        settings = self._settings()
        th = self._single_tool().get_status(self.reactor.monotonic())
        mesh = settings.get('bed_mesh', {})
        bounds, circle = self.bounds, None
        if bounds is None:
            if 'mesh_min' in mesh and 'mesh_max' in mesh:
                bounds = (mesh['mesh_min'], mesh['mesh_max'])
            elif 'mesh_radius' in mesh:
                circle = (mesh.get('mesh_origin', (0., 0.)), mesh['mesh_radius'])
        bc = settings['beacon']
        return edge_point(th['axis_minimum'][:2], th['axis_maximum'][:2],
                          (bc.get('x_offset', 0.), bc.get('y_offset', 0.)),
                          self.margin, bounds, circle, self.point)

    def _allowed(self, gcmd, names):
        unexpected = set(gcmd.get_command_parameters()) - set(names)
        if unexpected:
            raise ValueError('Unknown parameter(s): %s' % ', '.join(sorted(unexpected)))

    def _validate_interval(self, low, high):
        finite(low, 'LOW_TEMP', 50., 350.)
        finite(high, 'HIGH_TEMP', 50., 350.)
        if high - low < 30.:
            raise ValueError('HIGH_TEMP must exceed LOW_TEMP by at least 30 C')
        settings = self._settings()
        ceiling = min(finite(settings['extruder']['max_temp'], 'heater max_temp', 50., 1000.) - 5.,
                      finite(settings['beacon'].get('contact_max_hotend_temperature', 180.),
                             'contact_max_hotend_temperature', 50., 1000.) - 2.)
        if high > ceiling:
            raise ValueError('HIGH_TEMP exceeds hotend/contact limit (%g C). '
                             'Choose a suitable surface and explicitly configure Beacon; '
                             'KAT never raises hardware temperature limits' % ceiling)

    def _idle_geometry(self):
        th = self._single_tool()
        status = th.get_status(self.reactor.monotonic())
        if status['homed_axes'] != 'xyz':
            raise ValueError('Home and level with a cool nozzle first; this test never homes')
        if float(status['axis_maximum'][2]) < self.clearance:
            raise ValueError('Z travel is too small for calibration clearance')
        for name, key, bad in [('print_stats', 'state', ('printing', 'paused')),
                               ('virtual_sdcard', 'is_active', (True,)),
                               ('pause_resume', 'is_paused', (True,))]:
            obj = self.printer.lookup_object(name, None)
            if obj is not None and obj.get_status(self.reactor.monotonic()).get(key) in bad:
                raise ValueError('Calibration requires an idle, unpaused printer')
        mesh = self.printer.lookup_object('bed_mesh', None)
        if mesh is not None and mesh.get_mesh() is not None:
            raise ValueError('Run BED_MESH_CLEAR before the calibration')
        skew = self.printer.lookup_object('skew_correction', None)
        if skew is not None and any(abs(getattr(skew, k, 0.)) > 1.e-12
                                    for k in ('xy_factor', 'xz_factor', 'yz_factor')):
            raise ValueError('Run SET_SKEW CLEAR=1 before the calibration')
        bed = self.printer.lookup_object('heater_bed', None)
        if bed is not None:
            status = bed.get_status(self.reactor.monotonic())
            actual = finite(status['temperature'], 'bed temperature', 0., 1000.)
            target = finite(status['target'], 'bed target', 0., 1000.)
            if target != 0. or actual > self.max_bed_temp:
                raise ValueError('Turn off the bed and let it cool below %g C first' % self.max_bed_temp)
        self._variables()
        return th

    def _script(self, text):
        self.gcode.run_script_from_command(text)

    def _heater_off(self):
        heater = self._object('extruder').get_heater()
        self._object('heaters').set_temperature(heater, 0., False)

    def _wait_temperature(self, target):
        self._script('SET_HEATER_TEMPERATURE HEATER=extruder TARGET=%.6f' % target)
        heater = self._object('extruder').get_heater()
        start, stable = self.reactor.monotonic(), None
        while True:
            now = self.reactor.monotonic()
            if self.printer.is_shutdown():
                raise ValueError('Printer shut down during temperature calibration')
            actual, commanded = heater.get_temp(now)
            if abs(commanded - target) > .01:
                raise ValueError('Nozzle target changed during calibration')
            if now - start > self.timeout:
                raise ValueError('Timed out waiting for stable nozzle temperature')
            self._object('toolhead').get_last_move_time()
            if abs(actual - target) <= 1.:
                stable = now if stable is None else stable
                if now - stable >= self.settle:
                    return
            else:
                stable = None
            self.reactor.pause(now + .5)

    def _probe(self, samples=5):
        self._script('PROBE PROBE_METHOD=contact PROBE_SPEED=3 LIFT_SPEED=15 '
                     'SAMPLES=%d SAMPLE_RETRACT_DIST=3 SAMPLES_TOLERANCE=0.005 '
                     'SAMPLES_TOLERANCE_RETRIES=10 SAMPLES_RESULT=median' % samples)
        status = self._object('beacon').get_status(self.reactor.monotonic())
        if status.get('last_probe_result') != 'ok':
            raise ValueError('Beacon did not report a successful Contact measurement')
        value = finite(status.get('last_z_result'), 'Beacon last_z_result')
        self._script('G0 Z%.6f F300' % self.clearance)
        return value

    def cmd_calibrate(self, gcmd):
        try:
            self._allowed(gcmd, ('RUN', 'LOW_TEMP', 'HIGH_TEMP'))
            if self.running:
                raise ValueError('Calibration is already running')
            low = finite(gcmd.get('LOW_TEMP', self.low), 'LOW_TEMP')
            high = finite(gcmd.get('HIGH_TEMP', self.high), 'HIGH_TEMP')
            run = gcmd.get_int('RUN', 0, minval=0, maxval=1)
            point = self._point()
            self._validate_interval(low, high)
            gcmd.respond_info('EXPERIMENTAL KAT: nozzle point X=%.3f Y=%.3f; '
                              'two %.1f/%.1f C cycles, 5-sample medians; '
                              'verify clear metal/high-temperature surface and unload filament. '
                              'RUN=1 starts heating and Contact at this edge point.'
                              % (point[0], point[1], low, high))
            if not run:
                return
            th = self._idle_geometry()
        except ValueError as e:
            raise gcmd.error(str(e))
        saved = False
        idle = self.printer.lookup_object('idle_timeout', None)
        old_timeout = getattr(idle, 'idle_timeout', None)
        old_applied, old_reference = self.applied, self.reference
        self.running = True
        self.last_result = 'running'
        try:
            # Save modes/offsets only. MOVE=0 restoration NEVER returns a hot nozzle to center.
            self._script('SAVE_GCODE_STATE NAME=KAT_BEACON_TEMPERATURE')
            saved = True
            if old_timeout is not None:
                self._script('SET_IDLE_TIMEOUT TIMEOUT=%.3f' % (5. * self.timeout + 300.))
            self._script('SET_GCODE_OFFSET X=0 Y=0 Z=0 MOVE=0')
            self.applied, self.reference = 0., None
            pos = th.get_position()
            # Normalize any G92 origin for physical bed coordinates; restore it in finally.
            self._script('G90\nG92 X%.6f Y%.6f Z%.6f' % tuple(pos[:3]))
            # Delta reach shrinks near the top; lower while still at the original XY.
            delta = self._settings().get('printer', {}).get('kinematics') == 'delta'
            travel_z = self.clearance if delta else max(pos[2], self.clearance)
            self._script('G0 Z%.6f F300\nG0 X%.6f Y%.6f F6000\nG0 Z%.6f F300\nM400'
                         % (travel_z, point[0], point[1], self.clearance))
            self._wait_temperature(low)
            self._probe(samples=10)  # Settle mechanics at the edge before recording data.
            readings = []
            for target in (low, high, low, high):
                self._wait_temperature(target)
                readings.append(self._probe())
                gcmd.respond_info('KAT temperature sample: %.1f C, Z=%.6f' % (target, readings[-1]))
            record = calibration_record(low, high, readings, self.agreement,
                                        self.max_coefficient, point)
            # One native save_variables write: metadata and coefficient commit together.
            # Preserve literal dict-key quotes through the G-code shlex parser.
            self._script('SAVE_VARIABLE VARIABLE=%s VALUE="%s"' % (KEY, repr(record)))
            self.last_result = 'saved'
            gcmd.respond_info('KAT saved expansion %.6f mm/100 C; cycles %.6f, %.6f. '
                              'Experimental print compensation enabled=%s. No SAVE_CONFIG needed.'
                              % (record['coefficient'], record['cycles'][0],
                                 record['cycles'][1], self.enabled))
        except ValueError as e:
            self.last_result = 'failed'
            raise gcmd.error(str(e))
        except Exception:
            self.last_result = 'failed'
            raise
        finally:
            # Direct heater API still runs if PROBE, a temperature wait, or persistence fails.
            try:
                self._heater_off()
            finally:
                try:
                    if saved and not self.printer.is_shutdown():
                        if old_timeout is not None:
                            self._script('SET_IDLE_TIMEOUT TIMEOUT=%.3f' % old_timeout)
                        self._script('RESTORE_GCODE_STATE NAME=KAT_BEACON_TEMPERATURE MOVE=0')
                finally:
                    self.applied, self.reference = old_applied, old_reference
                    self.running = False

    def _contributions(self, target, reference):
        self._single_tool()
        kat = self._kat()
        thermal = thermal_offset(self._variables().get(KEY), reference, target, self.max_coefficient)
        limit = finite(kat.get('z_offset_max_abs', 1.), 'KAT z_offset_max_abs', .001, 5.)
        user = 0.
        if kat.get('start_use_saved_z_offset', False):
            user = finite(self._variables().get('kat_print_z_offset', 0.), 'saved user offset', -limit, limit)
        finite(thermal + user, 'combined Z compensation', -limit, limit)
        return user, thermal

    def cmd_prepare(self, gcmd):
        try:
            self._allowed(gcmd, ('TARGET',))
            if not self.enabled:
                return
            if self.running:
                raise ValueError('Cannot start a print during temperature calibration')
            reference = finite(self._kat().get('start_preheat_temp', 150.), 'Contact reference')
            target = finite(gcmd.get('TARGET'), 'TARGET')
            self._contributions(target, reference)  # Fail before START_PRINT heats or homes.
            self._script('SET_GCODE_OFFSET Z=0 MOVE=0')
            self.applied, self.reference = 0., reference
        except ValueError as e:
            raise gcmd.error(str(e))

    def cmd_apply(self, gcmd):
        try:
            self._allowed(gcmd, ())
            if not self.enabled:
                raise ValueError('Experimental temperature compensation is disabled')
            if self.reference is None or self.running:
                raise ValueError('Run KAT_PREPARE_NOZZLE_TEMP_OFFSET TARGET=... before calibration/start')
            target = self._object('extruder').get_heater().get_temp(self.reactor.monotonic())[1]
            user, thermal = self._contributions(target, self.reference)
            self._script('SET_GCODE_OFFSET Z=%.9f MOVE=0' % (user + thermal))
            self.applied = thermal
            gcmd.respond_info('KAT Z: user=%.6f thermal=%.6f total=%.6f mm (no immediate move).'
                              % (user, thermal, user + thermal))
        except ValueError as e:
            raise gcmd.error(str(e))

    def cmd_show(self, gcmd):
        try:
            self._allowed(gcmd, ())
            gcmd.respond_info('EXPERIMENTAL KAT temperature: enabled=%s applied=%.6f mm '
                              'reference=%s C running=%s record=%s'
                              % (self.enabled, self.applied, self.reference,
                                 self.running, self._variables().get(KEY)))
        except ValueError as e:
            raise gcmd.error(str(e))

    def get_status(self, eventtime):
        return {'enabled': self.enabled, 'applied': self.applied,
                'reference_temp': self.reference, 'running': self.running,
                'last_result': self.last_result}


def load_config(config):
    return BeaconTemperature(config)
