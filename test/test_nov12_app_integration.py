"""Frozen daily wiring and retained real dispatch guards, not gameplay proof."""
import ast
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

from world.server import WorldServer
from test.test_daily_app_integration import BuildOptIn

ROOT = Path(__file__).resolve().parents[1]
OPTIONS = {
    'APPRENTICE_OUTINGS': 'apprentice-outings',
    'APPRENTICE_WALKING': 'apprentice-walking',
    'REMATCH_STRATEGIES': 'rematch-strategies',
    'FIELD_CONCEALMENT': 'field-concealment',
    'FIELD_SUPPORT': 'field-support',
    'ROUTE_TRAINERS': 'route-trainers',
    'PERSISTENT_CUT': 'persistent-cut',
    'MARKET_REACTIONS': 'market-reactions',
    'SHARED_BASE_ROOMS': 'base-rooms',
    'SHARED_CAVE_LIGHT': 'shared-cave-light',
    'SHARED_DEWFORD_TRENDS': 'dewford-trends',
    'SHARED_SAFARI_FEEDERS': 'safari-feeders',
    'SHARED_SOIL_CARE': 'shared-soil-care',
    'TRICK_QUIZ': 'trick-quiz',
}


class BuildWiring(unittest.TestCase):
    def test_actual_make_flags_off_and_on_without_turn_plan(self):
        harness = BuildOptIn()
        defaults = harness.flags()
        for name in OPTIONS:
            self.assertIn(f'-DEW_{name}=0', defaults)
        for enabled in (0, 1):
            flags = harness.flags(*(f'EW_{name}={enabled}' for name in OPTIONS))
            for name in OPTIONS:
                self.assertIn(f'-DEW_{name}={enabled}', flags)
            self.assertIn('-DEW_COOP_TURN_PLAN=0', flags)
            self.assertIn('-DEW_REGION_STATE=1', flags)
            self.assertIn('-DEW_KANTO_CONTENT=1', flags)

    def test_actual_builder_make_arguments_forward_each_switch(self):
        tree = ast.parse((ROOT / 'scripts/build_expansion.py').read_text())
        node = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.AugAssign)
                    and isinstance(n.target, ast.Name) and n.target.id == 'command'
                    and any(isinstance(x, ast.Constant) and x.value == 'make'
                            for x in ast.walk(n)))
        names = {n.attr for n in ast.walk(node)
                 if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                 and n.value.id == 'args'}
        for enabled in (False, True):
            args = SimpleNamespace(**{name: enabled for name in names})
            args.jobs = 1
            ns = dict(command=[], ROOT=ROOT, args=args, regional_state=1,
                      kanto_content=1, map_version='combined', compiler='gcc',
                      head='a'*40, RELEASE_CONFIG=SimpleNamespace(
                          map_version='combined',generated_world_regions=1,version_suffix='fixture'))
            exec(compile(ast.Module(body=[node], type_ignores=[]), 'actual-builder', 'exec'), ns)
            for name in OPTIONS:
                self.assertIn(f'EW_{name}={int(enabled)}', ns['command'])

    def test_all_new_cli_options_require_development(self):
        for suffix in OPTIONS.values():
            option = '--experimental-' + suffix
            with self.subTest(option=option):
                result = subprocess.run([sys.executable, str(ROOT/'scripts/build_expansion.py'), option],
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn('requires --development', result.stderr)


class RetainedAdmission(unittest.TestCase):
    def test_new_wire_dispatch_cannot_bypass_combined_registry(self):
        # Execute the actual class method with the real registry admission helper.
        peer = dict(id='a',state=[0,16,1,1,1,0,1],registry_wait=0)
        channel = dict(id='a',sock='socket',presence=peer)
        errors=[];queued=[]
        server = SimpleNamespace(combined_regions=True,peers={'a':peer},
            connections={'socket':channel},link_channels={'a':channel},
            _error=lambda c,e:errors.append(e),_queue=lambda c,v:queued.append(v))
        for packet in (b'RS GET 1 calvin',b'TQ GET 1',b'BC GET 1 1 1',
                       b'DT GET 1',b'TD GET 1',b'SF GET 1',b'FL STATE 1 1 1',
                       b'FS OFFER 1 b',b'PG CUT 1 x',b'B ROOM 1 x'):
            with self.subTest(packet=packet):
                errors.clear();queued.clear()
                WorldServer._link_line(server,channel,packet)
                self.assertEqual(errors,['REGISTRY_REQUIRED'])
                self.assertEqual(queued,[])
        # Replaced sessions are rejected before even consulting the registry.
        errors.clear()
        WorldServer._link_line(server,dict(channel),b'TQ GET 1')
        self.assertEqual(errors,[])


if __name__ == '__main__':
    unittest.main()
