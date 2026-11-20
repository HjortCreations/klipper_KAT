"""Exercise the optional installer in disposable firmware directories on Linux."""
# Distributed under GNU GPLv3; see ../LICENSE.
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'experimental/beacon_temperature/install.sh'


@unittest.skipUnless(os.name == 'posix', 'Installer targets Linux Klipper/Kalico hosts')
class InstallerTests(unittest.TestCase):
    def test_install_is_idempotent_and_leaves_other_files_alone(self):
        with TemporaryDirectory() as directory:
            extras = Path(directory) / 'klippy/extras'
            extras.mkdir(parents=True)
            other = extras / 'other.py'
            other.write_text('keep')
            for _ in range(2):
                subprocess.run(['sh', str(SCRIPT), directory], check=True, capture_output=True)
            link = extras / 'kat_beacon_temperature.py'
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), SCRIPT.with_name('kat_beacon_temperature.py').resolve())
            self.assertEqual(other.read_text(), 'keep')

    def test_refuses_foreign_file_and_missing_firmware_tree(self):
        with TemporaryDirectory() as directory:
            result = subprocess.run(['sh', str(SCRIPT), directory], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            extras = Path(directory) / 'klippy/extras'
            extras.mkdir(parents=True)
            target = extras / 'kat_beacon_temperature.py'
            target.write_text('unrelated module')
            result = subprocess.run(['sh', str(SCRIPT), directory], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_text(), 'unrelated module')


if __name__ == '__main__':
    unittest.main(verbosity=2)
