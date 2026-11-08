"""The build wrapper must verify/build before exporting generated metadata."""
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import build_expansion as build


class ExpansionBuildOrder(unittest.TestCase):
    def run_build(self, *, returncode=0, ancestry_failure=False):
        temporary = tempfile.TemporaryDirectory(prefix='ew-build-order-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source = root / 'engines/expansion-native'
        binaries = source / 'build/native64'
        binaries.mkdir(parents=True)
        (root / 'world').mkdir()
        catalogue = root / 'world/expansion_species.json'
        catalogue.write_text('original')
        events = []

        def command(argv, **kwargs):
            if argv[0] == 'git':
                events.append('ancestry')
                if ancestry_failure:
                    raise subprocess.CalledProcessError(1, argv)
                return SimpleNamespace(returncode=0)
            events.append('build')
            self.assertEqual(argv[0], 'bwrap')
            self.assertIn('--unshare-all', argv)
            for gate in ('data_relocations.checked', 'data_layout.checked', 'battle_script_operands.checked'):
                self.assertIn('build/native64/' + gate, argv)
            for name in ('pokeemerald-native', 'pokeemerald-native.symbols'):
                (binaries / name).write_text('built')
            return SimpleNamespace(returncode=returncode)

        def export(engine, output):
            events.append('export')
            self.assertEqual(engine, source)
            self.assertEqual(events[:3], ['ancestry', 'ancestry', 'build'])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text('new catalogue')

        with patch.object(build, 'ROOT', root), \
             patch('sys.argv', ['build_expansion.py']), \
             patch.object(build.subprocess, 'check_output', side_effect=[build.PIN+'\n', '']), \
             patch.object(build.subprocess, 'run', side_effect=command), \
             patch.object(build.shutil, 'which', return_value='/usr/bin/bwrap'), \
             patch('scripts.export_expansion_species_catalogue.export_catalogue', side_effect=export):
            if ancestry_failure:
                with self.assertRaises(subprocess.CalledProcessError):
                    build.main()
                result = None
            else:
                result = build.main()
        return root, events, result

    def test_export_and_artifacts_follow_successful_guarded_build(self):
        root, events, result = self.run_build()
        self.assertEqual(result, 0)
        self.assertEqual(events, ['ancestry', 'ancestry', 'build', 'export'])
        self.assertEqual((root/'world/expansion_species.json').read_text(), 'new catalogue')
        self.assertTrue((root/'build/expansion-native/pokeemerald-native').exists())

    def test_failed_build_does_not_replace_catalogue_or_publish_artifact(self):
        root, events, result = self.run_build(returncode=7)
        self.assertEqual(result, 7)
        self.assertNotIn('export', events)
        self.assertEqual((root/'world/expansion_species.json').read_text(), 'original')
        self.assertFalse((root/'build/expansion-native').exists())

    def test_failed_ancestry_cannot_execute_or_export_sources(self):
        root, events, _ = self.run_build(ancestry_failure=True)
        self.assertEqual(events, ['ancestry'])
        self.assertEqual((root/'world/expansion_species.json').read_text(), 'original')


if __name__ == '__main__':
    unittest.main()
