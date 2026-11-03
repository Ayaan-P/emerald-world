"""Public verification reports must never reproduce private subprocess output."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('windows_verify', ROOT / 'scripts/windows_verify.py')
assert SPEC is not None and SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)
SECRET = ('DO_NOT_PUBLISH_' + 'a9' * 32 + '\n-----BEGIN ' +
          'PRIVATE KEY-----\nprivate-data\n-----END PRIVATE KEY-----')
SOURCE = 'world/windows_client.py'


class WindowsDiagnosticsTests(unittest.TestCase):
    def run_program(self, program, timeout=5):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / 'result.json'
            result = subprocess.run(
                [sys.executable, str(ROOT / 'scripts/windows_verify.py'),
                 '--label', 'unit', '--timeout', str(timeout), '--report', str(report),
                 '--', sys.executable, '-c', program],
                capture_output=True, text=True, cwd=ROOT, timeout=15)
            data = json.loads(report.read_text())
            private = report.with_suffix('.private.log').read_text()
            public = json.dumps(data) + result.stdout + result.stderr
            for forbidden in (SECRET, 'DO_NOT_PUBLISH', 'a9' * 32, 'PRIVATE KEY', 'private-data'):
                self.assertNotIn(forbidden, public)
            return result, data, private

    def parse(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'synthetic.private.log'
            log.write_text(text, encoding='utf-8')
            return VERIFY.failure_diagnostics(log)

    def test_unittest_identifiers_are_bounded_and_no_subtest_values_escape(self):
        text = ('ERROR: test_run (test_windows_package.PackageTests.test_run)\n'
                'FAIL: test_bad (test_windows_package.PackageTests.test_bad) (secret=' + SECRET + ')\n'
                'ERROR: test_DO_NOT_PUBLISH (test_module.Tests.test_DO_NOT_PUBLISH)\n'
                'FAIL: test_' + 'a9' * 32 + ' (test_module.Tests.test_' + 'a9' * 32 + ')\n'
                'ERROR: test_run (other.Tests.test_different)\n'
                'ERROR: test_' + 'z' * 121 + ' (test_module.Tests.test_' + 'z' * 121 + ')\n')
        self.assertEqual(self.parse(text), [
            {'test_id': 'test_windows_package.PackageTests.test_run', 'outcome': 'ERROR'}])

    def test_unknown_formats_and_exception_names_are_private(self):
        for text in (
                SECRET, 'RuntimeError: ' + SECRET,
                '  File "world/windows_client.py", line 1, in run\nRuntimeError: ' + SECRET,
                'Traceback (most recent call last):\n  File "world/windows_client.py", line 1, in run\nDO_NOT_PUBLISHError: ' + SECRET,
                'ERROR test_run (test_module.Tests.test_run)\n' + SECRET):
            with self.subTest(format=text[:10]):
                self.assertEqual(self.parse(text), [])
        _, data, _ = self.run_program('import sys; print(' + repr(SECRET) + '); sys.exit(1)')
        self.assertNotIn('diagnostics', data)

    def test_unsafe_and_foreign_paths_never_escape(self):
        paths = ['/tmp/DO_NOT_PUBLISH.py', '../world/windows_client.py',
                 'world/../world/windows_client.py', 'world/missing.py',
                 'scripts/not_windows.py', 'world/' + 'a9' * 32 + '.py',
                 str(ROOT.parent / SOURCE), 'world/' + 'z' * 200 + '.py']
        for path in paths:
            text = ('Traceback (most recent call last):\n  File "' + path +
                    '", line 2, in run\nRuntimeError: ' + SECRET)
            self.assertEqual(self.parse(text), [{'exception_type': 'RuntimeError'}])
        text = ('Traceback (most recent call last):\n  File "' +
                str(ROOT / SOURCE).replace('/', '\\') +
                '", line 123, in run\nAssertionError: ' + SECRET)
        self.assertEqual(self.parse(text), [
            {'file': SOURCE, 'line': 123, 'exception_type': 'AssertionError'}])

    def test_only_last_64k_and_at_most_32_entries_are_parsed(self):
        block = ('Traceback (most recent call last):\n  File "' + SOURCE +
                 '", line 12, in run\nValueError: ' + SECRET + '\n')
        self.assertEqual(self.parse(block + 'x' * 65536), [])
        entries = self.parse(block * 200)
        self.assertEqual(len(entries), 32)
        self.assertTrue(all(entry == {'file': SOURCE, 'line': 12,
                                     'exception_type': 'ValueError'} for entry in entries))
        self.assertEqual(len(self.parse('ERROR: test_run (test_module.Tests.test_run)\n' * 100)), 32)
        frames = ('  File "' + SOURCE + '", line 12, in run\n') * 100
        self.assertEqual(len(self.parse('Traceback (most recent call last):\n' + frames + 'ValueError: secret')), 32)

    def test_success_remains_minimal_even_with_traceback_like_output(self):
        text = ('Traceback (most recent call last):\n  File "' + SOURCE +
                '", line 1, in run\nRuntimeError: ' + SECRET)
        result, data, private = self.run_program('print(' + repr(text) + ')')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(set(data), {'label', 'passed', 'timed_out', 'exit_code', 'seconds'})
        self.assertTrue(data['passed'])
        self.assertEqual(result.stdout, 'unit: PASS\n')
        self.assertIn(SECRET, private)

    def test_timeout_status_and_private_output_are_unchanged(self):
        result, data, private = self.run_program(
            'import time; print(' + repr(SECRET) + ', flush=True); time.sleep(30)', timeout=1)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(data['timed_out'])
        self.assertFalse(data['passed'])
        self.assertNotIn('diagnostics', data)
        self.assertIn(SECRET, private)

    def test_real_exception_retains_only_location_and_type(self):
        program = 'exec(compile(' + repr('raise RuntimeError(' + repr(SECRET) + ')') + ', ' + repr(str(ROOT / SOURCE)) + ', "exec"))'
        result, data, private = self.run_program(program)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(data['diagnostics'], [
            {'file': SOURCE, 'line': 1, 'exception_type': 'RuntimeError'}])
        self.assertIn('DO_NOT_PUBLISH', private)
        self.assertIn('PRIVATE KEY', private)
        self.assertEqual(result.stdout, 'unit: FAIL (see runner-local private log)\n')


if __name__ == '__main__':
    unittest.main()
