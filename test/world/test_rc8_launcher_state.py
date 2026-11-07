"""Player-facing area state from a real disposable owner authority; no model calls."""
from pathlib import Path
import tempfile
import unittest
from world.session import DesktopSession
from world.web_launcher import LauncherBridge
from world.xl_wilds import encode


class RC8AreaState(unittest.TestCase):
    def test_current_area_reports_real_dimensions_and_occupancy(self):
        with tempfile.TemporaryDirectory(prefix='rc8ui-') as temp:
            session = DesktopSession(Path(temp))
            try:
                session.create_world('w')
                session.host('w')
                blob = encode({'rows': ['#'*127]+['#'+'.'*125+'#']*125+['#'*127],
                               'spawn': [1, 1], 'exit': [125, 125]})
                server = session.server
                server._replace_cave(blob, label='Wide islands')
                bridge = LauncherBridge(session, '/nonexistent/game')
                area = bridge.snapshot()['active_generated_area']
                self.assertEqual(area['label'], 'Wide islands')
                self.assertEqual(area['kind'], 'xl_wilds')
                self.assertEqual(area['side'], 127)
                self.assertEqual(area['occupants'], 0)
                with server.lock:
                    server.peers['fixture'] = {'id': 'Player', 'in_generated_cave': True,
                                              'state': None, 'closing': False}
                self.assertEqual(bridge.snapshot()['active_generated_area']['occupants'], 1)
                with server.lock:
                    server.peers.clear()
            finally:
                session.close()
