"""Compile production occupancy clearance; incomplete presence is not a landing proof."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class RecoveryOccupancyTests(unittest.TestCase):
    def test_clearance_requires_complete_fresh_travel_snapshot(self):
        source = (ROOT / 'src/platform/world_bridge.c').read_text()
        start = source.index('bool8 WorldBridge_TravelTileClear(')
        end = source.index('\n}\n', start) + 3
        prelude = r'''
#include <assert.h>
typedef unsigned char bool8;
#define TRUE 1
#define FALSE 0
struct Peer {unsigned group,num,x,y;};
struct TravelPeer {struct Peer peer; unsigned ttl;};
struct Tile {unsigned group,num,x,y;};
static struct {unsigned connected,snapshotAge; struct {unsigned travel,travelCount,peerCount,tileCount;struct TravelPeer friends[2];struct Peer peers[2];struct Tile tiles[2];} live;} sWorld;
static int MapCoords(unsigned g,unsigned n,unsigned x,unsigned y) {return g<10 && n<10 && x<100 && y<100;}
'''
        main = r'''
int main(void) {
 sWorld.connected=1;
 /* A current render-only snapshot omits offscreen occupants. */
 assert(!WorldBridge_TravelTileClear(1,1,4,5));
 sWorld.live.travel=1;assert(WorldBridge_TravelTileClear(1,1,4,5));
 sWorld.snapshotAge=181;assert(!WorldBridge_TravelTileClear(1,1,4,5));
 sWorld.snapshotAge=0;sWorld.live.travelCount=1;
 sWorld.live.friends[0]=(struct TravelPeer){{1,1,4,5},60};
 assert(!WorldBridge_TravelTileClear(1,1,4,5));
 assert(WorldBridge_TravelTileClear(1,1,5,5));
 sWorld.live.friends[0].ttl=0;assert(!WorldBridge_TravelTileClear(1,1,5,5));
 sWorld.live.travelCount=0;sWorld.live.tileCount=1;
 sWorld.live.tiles[0]=(struct Tile){1,1,4,5};
 assert(!WorldBridge_TravelTileClear(1,1,4,5));
 sWorld.live.tileCount=0;sWorld.connected=0;assert(!WorldBridge_TravelTileClear(1,1,4,5));
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='rc4-recovery-occupancy-') as directory:
            path = Path(directory)
            (path / 'probe.c').write_text(prelude + source[start:end] + main)
            result = subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(path / 'probe.c'), '-o', str(path / 'probe')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(path / 'probe')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
