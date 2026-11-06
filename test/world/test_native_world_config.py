"""Compile the complete production bridge and exercise its Linux config parser.

Requires a C compiler and generated engine headers, as for the native build.
The linker drops uncalled rendering/engine paths. This is not gameplay evidence.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('cc'), 'C compiler required')
class NativeWorldConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='ew-config-build-')
        cls.addClassCleanup(cls.build.cleanup)
        directory = Path(cls.build.name)
        harness = directory / 'config.c'
        cls.binary = directory / 'config'
        harness.write_text(r'''
#include "src/platform/world_bridge.c"
void WorldRally_Init(const char *configPath) { (void)configPath; }
int main(int argc, char **argv)
{
    if (argc > 2) return 3;
    if (!WorldBridge_Init(argc == 2 ? argv[1] : NULL))
        return WorldBridge_Enabled() ? 4 : 1;
    if (argc == 1)
        return WorldBridge_Enabled() || WorldBridge_TrainerName() != NULL;
    if (!WorldBridge_Enabled()) return 5;
    return strcmp(WorldBridge_TrainerName(), "alice") ? 6 : 0;
}
''')
        result = subprocess.run([
            'cc', '-std=gnu99', '-DPORTABLE', '-DMODERN=1', '-DNONMATCHING',
            '-DUBFIX', '-DVER_64BIT', '-Werror', '-Werror=implicit-function-declaration',
            '-ffunction-sections', '-fdata-sections', '-iquote', str(ROOT),
            '-iquote', str(ROOT / 'include'), str(harness), '-Wl,--gc-sections',
            '-o', str(cls.binary),
        ], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory(prefix='ew-config-')
        self.addCleanup(self.fixture.cleanup)
        self.path = Path(self.fixture.name) / 'world.conf'
        self.records = (b'socket /tmp/emerald-config-test.sock\ntrainer alice\ntoken '
                        + b'a' * 64 + b'\ntelemetry /tmp/emerald-config-test.json')

    def parse(self, content):
        self.path.write_bytes(content)
        result = subprocess.run([str(self.binary), str(self.path)],
                                capture_output=True, timeout=5)
        self.assertEqual(self.path.read_bytes(), content, 'configuration was mutated')
        return result

    def test_null_configuration_remains_disabled(self):
        result = subprocess.run([str(self.binary)], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_valid_lf_and_crlf_and_unterminated_final_record(self):
        for content in (self.records, self.records + b'\n',
                        (self.records + b'\n').replace(b'\n', b'\r\n')):
            with self.subTest(content=content):
                result = self.parse(content)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_horizontal_tabs_remain_valid_separators(self):
        result = self.parse(self.records.replace(b' ', b'\t'))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_visible_peer_preference_is_bounded_and_not_population(self):
        for limit in (1, 4, 8):
            with self.subTest(limit=limit):
                self.assertEqual(self.parse(self.records + f'\nvisible_peers {limit}\n'.encode()).returncode, 0)
        for value in ('0', '9', '32', '-1', '4294967296', 'four', '1\nvisible_peers 2'):
            with self.subTest(value=value):
                self.assertEqual(self.parse(self.records + f'\nvisible_peers {value}\n'.encode()).returncode, 1)

    def test_nul_cannot_hide_bytes_in_final_unterminated_record(self):
        for suffix in (b'\0', b'\0hidden', b'\0 extra value'):
            with self.subTest(suffix=suffix):
                result = self.parse(self.records + suffix)
                self.assertEqual(result.returncode, 1, 'embedded NUL was accepted')
                self.assertIn(b'Invalid world configuration.', result.stderr)

    def test_control_whitespace_cannot_substitute_for_separator(self):
        for separator in (b'\v', b'\f'):
            with self.subTest(separator=separator):
                result = self.parse(self.records.replace(b'trainer alice', b'trainer' + separator + b'alice'))
                self.assertEqual(result.returncode, 1, 'control separator was accepted')

    def test_control_bytes_in_path_or_comment_are_rejected(self):
        for byte in [value for value in range(32) if value not in (9, 10, 13)] + [127]:
            with self.subTest(byte=byte, location='path'):
                self.assertEqual(self.parse(self.records + bytes([byte])).returncode, 1)
            with self.subTest(byte=byte, location='comment'):
                self.assertEqual(self.parse(self.records + b'\n# ignored' + bytes([byte])).returncode, 1)

    def test_duplicate_and_unknown_fields_stay_invalid(self):
        for suffix in (b'\ntrainer alice\n', b'\nunknown value\n'):
            with self.subTest(suffix=suffix):
                self.assertEqual(self.parse(self.records + suffix).returncode, 1)


if __name__ == '__main__':
    unittest.main()
