"""Source setup failures must be actionable and leave tracked inputs untouched."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_expansion


class BuildSetup(unittest.TestCase):
    def test_feature_cohort_change_discards_stale_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            target = source / 'build/native64'
            target.mkdir(parents=True)
            stale = target / 'scripts.o'
            stale.touch()
            build_expansion.prepare_build_cohort(source, ['MAP_VERSION=combined'])
            self.assertFalse(stale.exists())
            stale.touch()
            build_expansion.prepare_build_cohort(source, ['MAP_VERSION=combined'])
            self.assertTrue(stale.exists())
            build_expansion.prepare_build_cohort(source, ['MAP_VERSION=emerald'])
            self.assertFalse(stale.exists())

    def test_release_rejects_gitlink_mismatch_before_toolchain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'engines/expansion-native'
            source.mkdir(parents=True)
            (source / 'Makefile.native').touch()
            (source / '.git').touch()
            errors = io.StringIO()
            with patch.object(build_expansion, 'ROOT', root), \
                    patch('sys.argv', ['build_expansion.py', '--check']), \
                    patch.object(build_expansion.subprocess, 'check_output',
                                 side_effect=[build_expansion.PIN, '', '0' * 40]), \
                    patch.object(build_expansion.subprocess, 'run') as run, \
                    contextlib.redirect_stderr(errors):
                with self.assertRaises(SystemExit):
                    build_expansion.main()
            self.assertIn('release pin mismatch', errors.getvalue())
            run.assert_not_called()

    def test_missing_bubblewrap_never_starts_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'engines/expansion-native'
            source.mkdir(parents=True)
            (source / 'Makefile.native').touch()
            (source / '.git').touch()
            errors = io.StringIO()
            with patch.object(build_expansion, 'ROOT', root), \
                    patch('sys.argv', ['build_expansion.py', '--check']), \
                    patch.object(build_expansion.subprocess, 'check_output',
                                 side_effect=[build_expansion.PIN, '', build_expansion.PIN]), \
                    patch.object(build_expansion.subprocess, 'run') as run, \
                    patch.object(build_expansion.shutil, 'which', return_value=None), \
                    contextlib.redirect_stderr(errors):
                with self.assertRaises(SystemExit):
                    build_expansion.main()
            self.assertIn('Bubblewrap is required', errors.getvalue())
            self.assertEqual(run.call_count, 2)  # ancestry checks only
            self.assertFalse((source / 'build').exists())

    def test_release_cohort_is_frozen(self):
        from dataclasses import FrozenInstanceError
        with self.assertRaises(FrozenInstanceError):
            setattr(build_expansion.RELEASE_CONFIG, 'kanto_content', 0)

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
            (root / 'engines/expansion.mk').write_text('# fixture wrapper\n')
            with patch.object(build_expansion, 'ROOT', root), \
                    patch('sys.argv', ['build_expansion.py']), \
                    patch.object(build_expansion.subprocess, 'check_output', side_effect=[build_expansion.PIN, '', build_expansion.PIN]), \
                    patch.object(build_expansion.subprocess, 'run', side_effect=[CompletedProcess([], 0), CompletedProcess([], 0), CompletedProcess([], 0), CompletedProcess([], 1)]) as run, \
                    patch.object(build_expansion.shutil, 'which', return_value='/usr/bin/bwrap'), \
                    patch('scripts.export_expansion_species_catalogue.export_catalogue') as export:
                self.assertEqual(build_expansion.main(), 1)
                export.assert_not_called()
                command = run.call_args.args[0]
                for expected in ('EW_REGION_STATE=1', 'EW_KANTO_CONTENT=1',
                                 'MAP_VERSION=combined', 'GENERATED_WORLD_REGIONS=0'):
                    self.assertIn(expected, command)
                self.assertIn('build/native64/data_layout.checked', command)

    def test_generated_region_flag_reaches_make_without_regional_saves(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'engines/expansion-native';source.mkdir(parents=True)
            (source/'Makefile.native').touch();(source/'.git').touch()
            from subprocess import CompletedProcess
            (root/'engines/expansion.mk').write_text('# fixture wrapper\n')
            with patch.object(build_expansion,'ROOT',root), patch('sys.argv',['build_expansion.py','--development','--generated-regions']), patch.object(build_expansion.subprocess,'check_output',side_effect=[build_expansion.PIN,'']), patch.object(build_expansion.subprocess,'run',side_effect=[CompletedProcess([],0),CompletedProcess([],0),CompletedProcess([],0),CompletedProcess([],1)]) as run, patch.object(build_expansion.shutil,'which',return_value='/usr/bin/bwrap'):
                self.assertEqual(build_expansion.main(),1)
                command=run.call_args.args[0]
                self.assertIn('GENERATED_WORLD_REGIONS=1',command)
                self.assertIn('EW_REGION_STATE=0',command)
                self.assertIn('EW_KANTO_CONTENT=0',command)

    def test_selectable_regions_preserve_combined_release_cohort(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'engines/expansion-native';source.mkdir(parents=True)
            (source/'Makefile.native').touch();(source/'.git').touch()
            (root/'engines/expansion.mk').write_text('# fixture wrapper\n')
            from subprocess import CompletedProcess
            with patch.object(build_expansion,'ROOT',root), patch('sys.argv',['build_expansion.py','--generated-regions']), patch.object(build_expansion.subprocess,'check_output',side_effect=[build_expansion.PIN,'',build_expansion.PIN]), patch.object(build_expansion.subprocess,'run',side_effect=[CompletedProcess([],0),CompletedProcess([],0),CompletedProcess([],0),CompletedProcess([],1)]) as run, patch.object(build_expansion.shutil,'which',return_value='/usr/bin/bwrap'):
                self.assertEqual(build_expansion.main(),1)
                command=run.call_args.args[0]
                for expected in ('GENERATED_WORLD_REGIONS=1','EW_REGION_STATE=1',
                                 'EW_KANTO_CONTENT=1','MAP_VERSION=combined'):
                    self.assertIn(expected,command)

    def test_check_mode_never_exports_or_builds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'engines/expansion-native'
            source.mkdir(parents=True)
            (source / 'Makefile.native').touch()
            (source / '.git').touch()
            with patch.object(build_expansion, 'ROOT', root), \
                    patch('sys.argv', ['build_expansion.py', '--check']), \
                    patch.object(build_expansion.subprocess, 'check_output', side_effect=[build_expansion.PIN, '', build_expansion.PIN]), \
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
