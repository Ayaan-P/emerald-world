"""Cross-map travel subscription regressions for the combined RC acceptance run."""
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from world.server import WorldServer, MAX_TRAVEL_PEERS
from world.rally import RallyCoordinator


class TravelRosterTests(unittest.TestCase):
    def setUp(self):
        self.server = WorldServer.__new__(WorldServer)
        self.server.cave_map = None
        self.server.wilds_map = None
        self.server.shared_cave = None
        self.server.revision = 1
        self.server.tiles = []
        self.server.objects = []
        self.server.peers = {}
        self.server.rally = RallyCoordinator(self.server.peers)
        self.server._queue = Mock()
        self.server._broadcast = Mock()
        self.server._error = Mock()
        self.server._event = Mock()
        self.server.db = sqlite3.connect(':memory:')
        self.addCleanup(self.server.db.close)
        self.server.db.execute('CREATE TABLE identities (id TEXT, token TEXT)')
        self.server.host_controls = SimpleNamespace(rejection=lambda name: None)
        self.server.max_players = 64

    def connect(self, name, role='SOCIALTRAVELCHAT', token=None):
        secret = 'ab' * 32
        self.server.db.execute('INSERT INTO identities VALUES (?, ?)', (name, secret))
        conn = dict(id=None, state=None, closing=False, seq=-1)
        self.server._line(conn, f'HELLO 1 {name} {token or secret} {role}'.encode())
        return conn

    @patch('world.server.time.monotonic', return_value=100)
    def test_cross_map_subscription_does_not_consume_render_slots(self, _clock):
        viewer = self.connect('viewer')
        viewer['state'] = [0, 9, 5, 5, 1, 7, 1]
        for i in range(63):
            peer = self.connect(f'friend{i:02}')
            peer.update(state=[0, 10 if i >= 8 else 9, 6, 6, 1, 7, 1],
                        field=True, state_time=100)
        frame = self.server._snapshot(viewer).splitlines()
        render = [line for line in frame if line.startswith('PEER ')]
        travel = [line for line in frame if line.startswith('FRIEND ')]
        self.assertEqual(len(render), 8)
        self.assertTrue(all(line.split()[3] == '9' for line in render))
        self.assertEqual(len(travel), MAX_TRAVEL_PEERS)
        self.assertIn('FRIEND friend62 0 10 6 6 1 7 1 180', travel)
        self.assertIn('TRAVEL 63', frame)
        self.assertTrue(viewer['chat'])
        old = dict(viewer, travel=False, chat=False)
        self.assertNotIn('FRIEND ', self.server._snapshot(old))
        self.assertNotIn('TRAVEL ', self.server._snapshot(old))

    @patch('world.server.time.monotonic', return_value=100)
    def test_freshness_is_per_trainer_and_busy_is_not_promoted_to_ready(self, _clock):
        viewer = self.connect('viewer')
        friend = self.connect('friend')
        friend.update(state=[0, 10, 6, 6, 1, 7, 0], field=True, state_time=98)
        self.assertIn('FRIEND friend 0 10 6 6 1 7 0 60', self.server._snapshot(viewer))
        friend['state_time'] = 96
        # Keep expired coordinates to fail closed on uncertain destination occupancy.
        self.assertIn('FRIEND friend 0 10 6 6 1 7 0 0', self.server._snapshot(viewer))
        friend['closing'] = True
        self.assertIn('TRAVEL 0', self.server._snapshot(viewer))
        self.assertNotIn('FRIEND ', self.server._snapshot(viewer))

    def test_authentication_and_legacy_roles_do_not_enable_travel(self):
        bad = self.connect('bad', token='cd' * 32)
        self.assertIsNone(bad['id'])
        self.assertNotIn('bad', self.server.peers)
        self.server._error.assert_called_with(bad, 'AUTH')
        chat = self.connect('chat', 'SOCIALCHAT')
        self.assertTrue(chat['chat'])
        self.assertFalse(chat['travel'])
        travel = self.connect('travel', 'SOCIALTRAVEL')
        self.assertTrue(travel['travel'])
        self.assertFalse(travel['chat'])


class TravelMenuPagingTests(unittest.TestCase):
    def test_all_world_friends_fit_bounded_menu_pages(self):
        import pathlib
        import subprocess
        import tempfile
        from test.world.test_save_isolation import function
        root = pathlib.Path(__file__).resolve().parents[2]
        source = r'''
#include <assert.h>
#include <string.h>
#include <stdio.h>
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
#define FONT_SMALL 0
#define COPYWIN_FULL 0
#define TRAVEL_FRIENDS 2
struct WorldBridgePeer { char name[25]; unsigned group,num,x,y; int ready; };
static struct { unsigned window,count,page,state; int nextPage; char names[6][25]; const char *status; } sTravel;
static unsigned available=63, choices, seen[63];
static int TravelWindow(void) { return 1; }
static void TravelPrint(const char *text, unsigned y) {
    unsigned n;
    assert(y < 144);
    if (sscanf(text,"friend%u",&n)==1) { assert(n<63); seen[n]++; }
}
static int WorldBridge_GetTravelPeer(unsigned i, struct WorldBridgePeer *p) {
    if (i>=available) return 0;
    sprintf(p->name,"friend%02u",i); return 1;
}
static void InitMenuNormal(unsigned w,unsigned f,unsigned x,unsigned y,unsigned h,unsigned n,unsigned c) {
    (void)w;(void)f;(void)x;(void)y;(void)h;(void)c; choices=n;
}
static void CopyWindowToVram(unsigned w,unsigned m) { (void)w;(void)m; }
''' + function((root / 'src/platform/world_travel.c').read_text(), 'TravelFriends') + r'''
int main(void) {
    for (unsigned page=0; page<11; page++) {
        sTravel.page=page; TravelFriends();
        assert(choices<=9);
        assert(sTravel.nextPage==(page<10));
    }
    for (unsigned i=0;i<63;i++) assert(seen[i]==1);
    available=1; sTravel.page=10; TravelFriends();
    assert(sTravel.page==0 && sTravel.count==1 && choices==2);
    available=0; TravelFriends();
    assert(sTravel.count==0 && choices==1);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='ew-friend-pages-') as directory:
            path = pathlib.Path(directory)
            c, binary = path / 'pages.c', path / 'pages'
            c.write_text(source)
            result = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()

