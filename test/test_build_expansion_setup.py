"""Source setup failures must be actionable and leave tracked inputs untouched."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_expansion


class BuildSetup(unittest.TestCase):
    def test_missing_sysroot_is_an_argument_error(self):
        errors = io.StringIO()
        with patch('sys.argv', ['build_expansion.py', '--sysroot', '/nonexistent/emerald-world-sysroot']), \
                contextlib.redirect_stderr(errors):
            with self.assertRaises(SystemExit) as failure:
                build_expansion.main()
        self.assertEqual(failure.exception.code, 2)
        self.assertIn('--sysroot must name an existing directory', errors.getvalue())

    def test_uninitialized_submodule_does_not_export_catalogue(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'engines/expansion-native').mkdir(parents=True)
            errors = io.StringIO()
            with patch.object(build_expansion, 'ROOT', root), \
                    patch('sys.argv', ['build_expansion.py']), \
                    patch('scripts.export_expansion_species_catalogue.export_catalogue') as export, \
                    contextlib.redirect_stderr(errors):
                with self.assertRaises(SystemExit) as failure:
                    build_expansion.main()
            self.assertEqual(failure.exception.code, 2)
            self.assertIn('git submodule update --init --recursive', errors.getvalue())
            export.assert_not_called()
            self.assertFalse((root / 'build').exists())
    def test_wrong_pin_explains_update_without_exporting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'engines/expansion-native'
            source.mkdir(parents=True)
            (source / 'Makefile.native').touch()
            (source / '.git').touch()
            errors = io.StringIO()
            with patch.object(build_expansion, 'ROOT', root), \
                    patch('sys.argv', ['build_expansion.py']), \
                    patch.object(build_expansion.subprocess, 'check_output', side_effect=['0' * 40, '']), \
                    patch('scripts.export_expansion_species_catalogue.export_catalogue') as export, \
                    contextlib.redirect_stderr(errors):
                with self.assertRaises(SystemExit):
                    build_expansion.main()
            self.assertIn('git submodule update --init --recursive', errors.getvalue())
            export.assert_not_called()

    def test_failed_build_does_not_export_from_unprepared_fresh_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'engines/expansion-native'
            source.mkdir(parents=True)
            (source / 'Makefile.native').touch()
            (source / '.git').touch()
            from subprocess import CompletedProcess
            with patch.object(build_expansion, 'ROOT', root), \
                    patch('sys.argv', ['build_expansion.py']), \
                    patch.object(build_expansion.subprocess, 'check_output', side_effect=[build_expansion.PIN, '']), \
                    patch.object(build_expansion.subprocess, 'run', side_effect=[CompletedProcess([], 0), CompletedProcess([], 0), CompletedProcess([], 0), CompletedProcess([], 1)]), \
                    patch.object(build_expansion.shutil, 'which', return_value='/usr/bin/bwrap'), \
                    patch('scripts.export_expansion_species_catalogue.export_catalogue') as export:
                self.assertEqual(build_expansion.main(), 1)
                export.assert_not_called()

    def test_check_mode_never_exports_or_builds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'engines/expansion-native'
            source.mkdir(parents=True)
            (source / 'Makefile.native').touch()
            (source / '.git').touch()
            with patch.object(build_expansion, 'ROOT', root), \
                    patch('sys.argv', ['build_expansion.py', '--check']), \
                    patch.object(build_expansion.subprocess, 'check_output', side_effect=[build_expansion.PIN, '']), \
                    patch.object(build_expansion.subprocess, 'run') as run, \
                    patch.object(build_expansion.shutil, 'which', return_value='/usr/bin/bwrap'), \
                    patch('scripts.export_expansion_species_catalogue.export_catalogue') as export:
                run.return_value.returncode = 0
                self.assertEqual(build_expansion.main(), 0)
                export.assert_not_called()
                self.assertFalse((root / 'build').exists())
                self.assertFalse(any('make' in call.args[0] for call in run.call_args_list))


if __name__ == '__main__':
    unittest.main()
