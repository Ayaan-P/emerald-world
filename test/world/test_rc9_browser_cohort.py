"""Browser integration regressions; disposable authority, no provider calls."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest
from world.session import DesktopSession
from world.web_launcher import LauncherBridge

class RC9Browser(unittest.TestCase):
    def test_authoring_passes_selected_engine_species_cohort(self):
        for engine in ('vanilla', 'expansion-native'):
            with self.subTest(engine=engine), tempfile.TemporaryDirectory() as temp:
                session=DesktopSession(Path(temp),engine=engine)
                try:
                    session.create_world('w');session.host('w')
                    bridge=LauncherBridge(session,'/nonexistent/game',engine=engine)
                    with patch.object(session,'author_shared_cave') as author:
                        bridge.action('author_cave',dict(world='w',confirmed=True,theme='forest',kind='cave'))
                        self.assertEqual(author.call_args.kwargs.get('cohort'),engine)
                finally:session.close()

    def test_wire_version_classification_does_not_confuse_expansion_wildlife_with_xl(self):
        with tempfile.TemporaryDirectory() as temp:
            session=DesktopSession(Path(temp),engine='expansion-native')
            try:
                session.create_world('w');session.host('w')
                bridge=LauncherBridge(session,'/nonexistent/game',engine='expansion-native')
                # Snapshot-only unit fixtures. No fixture is admitted as a game map.
                for version,side,kind in ((16,127,'xl_wilds'),(10,31,'cave'),(11,63,'cave')):
                    with self.subTest(version=version):
                        session.server.shared_cave=SimpleNamespace(version=version,side=side,identity='a'*64)
                        self.assertEqual(bridge.snapshot()['active_generated_area']['kind'],kind)
                session.server.shared_cave=None
            finally:session.close()
