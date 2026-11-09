"""Private Expansion handoff tests. PE fixtures are synthetic, never runtime proof."""
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/windows_expansion_package.py'


def load():
    spec = importlib.util.spec_from_file_location('delivery', SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pe(dll=False):
    data = bytearray(512)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 128)
    data[128:132] = b'PE\0\0'
    struct.pack_into('<H', data, 132, 0x8664)
    struct.pack_into('<H', data, 150, 0x2002 if dll else 2)
    struct.pack_into('<H', data, 152, 0x20b)
    return bytes(data)


class DeliveryTests(unittest.TestCase):
    def test_all_runtime_catalogues_are_mandatory(self):
        from unittest.mock import patch
        d = load()
        required = {'world/expansion_species.json', 'world/map_catalog.json',
                    'world/trainer_reference.json', 'world/trainer_experience_catalog.json'}
        base = {name: b'{}' for name in required}
        base.update({'world/windows_client.py': b'', 'launcher-web/index.html': b'', d.ENTRY: b''})
        for absent in required:
            payload = {name: data for name, data in base.items() if name != absent}
            records = b''.join(b'100644 blob '+b'a'*40+b'\t'+name.encode()+b'\0' for name in payload)
            def fake_git(root, *args):
                return records if args[0] == 'ls-tree' else payload[args[1].split(':', 1)[1]]
            with self.subTest(absent=absent), patch.object(d, 'git', side_effect=fake_git):
                with self.assertRaisesRegex(ValueError, 'missing'):
                    d.pinned_sources(ROOT, 'a'*40)

    def test_current_bundle_contains_every_local_module_and_loads_runtime_catalogues(self):
        import ast
        import subprocess
        import tempfile
        import sys
        d = load()
        # This audit needs only committed world/UI inputs, not the newly added
        # entry script before its first commit. The entry is tested separately.
        from unittest.mock import patch
        with patch.object(d, 'ENTRY', 'world/__init__.py'):
            payload = d.pinned_sources(ROOT, d.git(ROOT, 'rev-parse', 'HEAD').decode().strip())
        for name, data in payload.items():
            if not name.startswith('world/') or not name.endswith('.py'):
                continue
            for node in ast.walk(ast.parse(data, filename=name)):
                modules = []
                if isinstance(node, ast.ImportFrom):
                    if node.level == 1:
                        modules = [node.module.split('.')[0]] if node.module else [a.name for a in node.names]
                    elif node.module == 'world':
                        modules = [a.name for a in node.names]
                    elif node.module and node.module.startswith('world.'):
                        modules = [node.module.split('.')[1]]
                elif isinstance(node, ast.Import):
                    modules = [a.name.split('.')[1] for a in node.names if a.name.startswith('world.')]
                for module in modules:
                    self.assertIn('world/'+module+'.py', payload, (name, module))
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in payload.items():
                path = Path(tmp)/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            subprocess.run([sys.executable, '-B', '-c',
                'from world import windows_client; from world.trainer_experiences import catalog; '
                'from world.trainer_context import author_context; from world.build_catalog import catalog_maps; '
                'from world.species_cohort import CATALOGUE_PATH; '
                'assert catalog(); assert author_context("Rustboro")["summary"]; '
                'assert catalog_maps(); assert CATALOGUE_PATH.is_file()'], cwd=tmp, check=True)

    def test_regions_match_approved_linux_cohort(self):
        self.assertEqual(load().FLAGS['GENERATED_WORLD_REGIONS'], '0')

    def test_expansion_guest_uses_native_cli_and_private_environment(self):
        import json
        import os
        import tempfile
        from world.windows_client import WindowsGuestSession
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            invitation = root/'invitation.json'
            invitation.write_text(json.dumps({'trainer': 'Tester', 'token': 'a'*64}))
            binary = root/'pokeemerald-native.exe'
            binary.write_bytes(b'test fixture, not executable')
            session = WindowsGuestSession('localhost', 8765, 'b'*64, invitation,
                data_root=root/'profiles', binary=binary, engine='expansion-native')
            try:
                session.prepare()
                args = session.game_args()
                self.assertNotIn('--world-config', args)
                self.assertNotIn('--config', args)
                self.assertIn('--data-dir', args)
                self.assertIn('--rtc-offset', args)
                self.assertIn('expansion-native', session.paths['profile'].parts)
                env = session.game_environment()
                self.assertEqual(env['EW_WORLD_CONFIG'], str(session.paths['config']))
                self.assertNotIn('EW_PLAYER_CONTROL', env)
                self.assertEqual(session.paths['save'].parent, session.paths['profile'])
            finally:
                session.close()

    def test_build_sandbox_supports_private_multilib_without_global_install(self):
        import sys
        sys.path.insert(0, str(ROOT/'scripts'))
        import windows_expansion_build as build
        args = build.sandbox(Path('/engine'), Path('/private/multilib'))
        self.assertIn('/private/multilib/lib32/ld-linux.so.2', args)
        self.assertIn('/lib/ld-linux.so.2', args)

    def test_actual_x64_pe_required_not_mz_or_elf(self):
        self.assertTrue(SCRIPT.exists(), 'missing Expansion-specific PE verifier')
        delivery = load()
        delivery.check_pe(pe(), dll=False)
        for bad in (b'MZfake', b'\x7fELF', pe(True)):
            with self.assertRaises(ValueError):
                delivery.check_pe(bad, dll=False)

    def test_recursive_dll_closure_records_system_edges(self):
        d = load()
        self.assertTrue(hasattr(d, 'dll_closure'), 'missing DLL closure verifier')
        graph = {'game.exe': ['SDL2.dll', 'KERNEL32.dll'],
                 'SDL2.dll': ['libwinpthread-1.dll'], 'libwinpthread-1.dll': ['WS2_32.dll']}
        files, edges = d.dll_closure(Path('game.exe'),
            [Path('SDL2.dll'), Path('libwinpthread-1.dll')], lambda p: graph[p.name])
        self.assertEqual([p.name for p in files], ['libwinpthread-1.dll', 'SDL2.dll'])
        self.assertEqual(edges['game.exe']['system'], ['kernel32.dll'])
        with self.assertRaisesRegex(ValueError, 'Unresolved'):
            d.dll_closure(Path('game.exe'), [Path('SDL2.dll')], lambda p: graph[p.name])
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            d.dll_closure(Path('game.exe'), [Path('SDL2.dll'), Path('sdl2.DLL')], lambda p: graph[p.name])
        with self.assertRaises(ValueError):
            d.dll_closure(Path('game.exe'), [], lambda p: ['../evil.dll'])
    def test_source_allowlist_traversal_and_secrets_fail_closed(self):
        d = load()
        self.assertTrue(hasattr(d, 'check_source'), 'missing bounded source policy')
        d.check_source('world/windows_client.py', b'import json\n')
        d.check_source('launcher-web/index.html', b'<html>')
        for name, data in [('world/../invite.json', b'{}'), ('world/profile.sav', b'game'),
                           ('world/.env', b'KEY=value'), ('world/a.py', b'-----BEGIN PRIVATE KEY-----'),
                           ('world/invite.json', b'{"token":"private"}'),
                           ('world/a.py', b'x = "ghp_' + b'a'*36 + b'"'),
                           ('world/a.py', b'x = "sk-proj-' + b'a'*40 + b'"')]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                d.check_source(name, data)

    def test_receipt_requires_exact_cohort_and_flags(self):
        d = load()
        self.assertTrue(hasattr(d, 'verify_receipt'), 'missing build receipt verifier')
        receipt = {'schema': 1, 'engine': 'expansion-native', 'app_commit': 'a'*40,
                   'engine_commit': 'b'*40, 'flags': {'BITS': '64', 'TARGET_OS': 'windows',
                   'EW_REGION_STATE': '1', 'EW_KANTO_CONTENT': '1', 'GENERATED_WORLD_REGIONS': '0',
                   'MAP_VERSION': 'combined'}, 'binary_sha256': d.sha256(pe()),
                   'integration_sha256': d.sha256(b'flags'), 'command': ['make'], 'tools': {'gcc': 'test'}}
        d.verify_receipt(receipt, 'a'*40, 'b'*40, pe(), b'flags')
        for key, value in [('engine', 'vanilla'), ('app_commit', 'c'*40),
                           ('engine_commit', 'd'*40), ('binary_sha256', '0'*64),
                           ('integration_sha256', '0'*64), ('flags', {'BITS': '32'})]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                d.verify_receipt(dict(receipt, **{key: value}), 'a'*40, 'b'*40, pe(), b'flags')

    def test_archive_roundtrip_has_no_profiles_and_hashes_every_payload(self):
        import tempfile
        import zipfile
        import json
        d = load()
        self.assertTrue(hasattr(d, 'write_archive'), 'missing local archive writer')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'private.zip'
            payload = {'world/windows_client.py': b'import json\n',
                       'game/pokeemerald-native.exe': pe()}
            d.write_archive(payload, {'engine': 'expansion-native'}, output)
            with zipfile.ZipFile(output) as z:
                manifest = json.loads(z.read('provenance.json'))
                self.assertEqual(set(z.namelist()), set(payload) | {'provenance.json'})
                for name, data in payload.items():
                    self.assertEqual(manifest['files'][name], d.sha256(z.read(name)))
            with self.assertRaises(ValueError):
                d.write_archive({'../escape': b'x'}, {}, Path(tmp)/'bad.zip')
            with self.assertRaises(ValueError):
                d.write_archive(payload, {}, output)

    def test_end_to_end_pinned_sources_binary_and_dependency_manifest(self):
        import tempfile
        import subprocess
        import json
        import zipfile
        d = load()
        self.assertTrue(hasattr(d, 'assemble'), 'missing pinned package assembly')
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)/'app'
            engine = app/'engines/expansion-native'
            engine.mkdir(parents=True)
            def git(root, *args):
                return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
            for root in (app, engine):
                git(root, 'init', '-q')
                git(root, 'config', 'user.email', 'test@example.invalid')
                git(root, 'config', 'user.name', 'Test')
                git(root, 'config', 'advice.addEmbeddedRepo', 'false')
            (engine/'Makefile.native').write_text('# synthetic fixture\n')
            (engine/'.gitignore').write_text('build/\n')
            git(engine, 'add', '.')
            git(engine, 'commit', '-qm', 'engine fixture')
            engine_pin = git(engine, 'rev-parse', 'HEAD')
            for name, data in {'world/windows_client.py': b'import json\n',
                    'world/expansion_species.json': b'{"cohort":"expansion-native"}',
                    'world/map_catalog.json': b'{}',
                    'world/trainer_reference.json': b'{}',
                    'world/trainer_experience_catalog.json': b'{"trainers":{}}',
                    'launcher-web/index.html': b'<html>',
                    'scripts/windows_expansion_entry.py': b'# entry\n',
                    'engines/expansion.mk': b'# flags\n', '.gitignore': b'build/\n'}.items():
                p = app/name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
            git(app, 'add', 'world', 'launcher-web', 'scripts', 'engines/expansion.mk', '.gitignore')
            git(app, 'update-index', '--add', '--cacheinfo', '160000', engine_pin, 'engines/expansion-native')
            git(app, 'commit', '-qm', 'app fixture')
            app_pin = git(app, 'rev-parse', 'HEAD')
            binary = engine/'build/native64-windows/pokeemerald-native.exe'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(pe())
            dll = binary.with_name('SDL2.dll')
            dll.write_bytes(pe(True))
            receipt = {'schema': 1, 'engine': 'expansion-native', 'app_commit': app_pin,
                'engine_commit': engine_pin, 'flags': d.FLAGS, 'command': ['fixture'],
                'tools': {'fixture': 'not a build'}, 'binary_sha256': d.sha256(pe()),
                'integration_sha256': d.sha256(b'# flags\n')}
            receipt['source_sha256'] = {n: d.sha256(b) for n, b in d.pinned_sources(app, app_pin).items()}
            receipt['catalogue_sha256'] = d.sha256((app/'world/expansion_species.json').read_bytes())
            rp = binary.with_name('windows-expansion-build.json')
            rp.write_text(json.dumps(receipt))
            output = Path(tmp)/'private.zip'
            d.assemble(app, app_pin, engine_pin, rp, [binary.parent], output,
                imports=lambda p: ['SDL2.dll'] if p.suffix == '.exe' else ['KERNEL32.dll'])
            with zipfile.ZipFile(output) as z:
                manifest = json.loads(z.read('provenance.json'))
                self.assertEqual(manifest['build']['app_commit'], app_pin)
                self.assertIn('game/SDL2.dll', manifest['files'])
                self.assertEqual(manifest['dll_imports']['SDL2.dll']['system'], ['kernel32.dll'])
                self.assertIn('world/windows_client.py', manifest['files'])
                self.assertIn('launcher-web/index.html', manifest['files'])
                self.assertNotIn('world/invite.json', manifest['files'])
            stage = Path(tmp)/'extracted'
            with zipfile.ZipFile(output) as z:
                z.extractall(stage)
            spec = importlib.util.spec_from_file_location('entry', ROOT/'scripts/windows_expansion_entry.py')
            assert spec is not None and spec.loader is not None
            entry = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(entry)
            self.assertEqual(entry.verify(stage), stage/'game/pokeemerald-native.exe')
            (stage/'world/windows_client.py').write_text('# tampered')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                entry.verify(stage)
            receipt['source_sha256']['world/windows_client.py'] = '0'*64
            rp.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'source'):
                d.assemble(app, app_pin, engine_pin, rp, [binary.parent], Path(tmp)/'wrong-source.zip',
                           imports=lambda p: [])
            binary.write_bytes(b'MZlegacy')
            with self.assertRaises(ValueError):
                d.assemble(app, app_pin, engine_pin, rp, [binary.parent], Path(tmp)/'bad.zip', imports=lambda p: [])

    def test_link_and_windows_reserved_paths_rejected(self):
        import tempfile
        d = load()
        for name in ('../x', '/root', 'game\\x.dll', 'game/CON.dll', 'world/x.py.', 'game/C:x.dll'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                d.safe_name(name)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'link'
            p.symlink_to(Path(tmp)/'missing')
            with self.assertRaises(ValueError):
                d.plain_path(p)

    def test_build_lane_reports_missing_tools_without_downloads(self):
        import subprocess
        script = ROOT/'scripts/windows_expansion_build.py'
        self.assertTrue(script.exists(), 'missing actual Expansion build entry')
        result = subprocess.run(['python3', str(script), '--check', '--app-pin', 'a'*40,
                                 '--engine-pin', 'b'*40], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Nothing was installed or downloaded', result.stderr)

    def test_runtime_entry_rejects_linux_before_importing_guest(self):
        import subprocess
        import sys
        if sys.platform == 'win32':
            self.skipTest('Linux unsupported-platform test')
        script = ROOT/'scripts/windows_expansion_entry.py'
        self.assertTrue(script.exists(), 'missing source-handoff entry')
        result = subprocess.run(['python3', str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Windows x64', result.stderr)

    def test_workflow_never_uploads_or_builds_game_payload(self):
        workflow = (ROOT/'.github/workflows/windows-expansion-source-gates.yml').read_text()
        self.assertNotRegex(workflow, r'uses:\s*actions/upload-artifact')
        self.assertNotRegex(workflow, r'contents:\s*write|gh release|gh workflow')
        self.assertIn('submodules: false', workflow)
        self.assertIn('python3 -m unittest test.test_windows_expansion_delivery', workflow)

    def test_production_world_and_ui_sources_fit_bounded_policy(self):
        import subprocess
        d = load()
        names = subprocess.check_output(['git', '-C', str(ROOT), 'ls-tree', '-r', '--name-only',
                                         'HEAD', 'world', 'launcher-web'], text=True).splitlines()
        for name in names:
            if name.endswith('.md') or name == 'launcher-web/.gitignore' or '.test.' in name or '.spec.' in name:
                continue
            data = subprocess.check_output(['git', '-C', str(ROOT), 'show', 'HEAD:'+name])
            with self.subTest(name=name):
                d.check_source(name, data)


if __name__ == '__main__':
    unittest.main()
