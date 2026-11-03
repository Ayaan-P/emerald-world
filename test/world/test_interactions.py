"""Trainer social signals exercise the authority and actual extracted native C."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT.parent / 'emerald-world-research'


class TrainerInteractions(unittest.TestCase):
    def test_actual_native_input_and_dialogue_wait_for_authority(self):
        from test_save_isolation import function
        bridge = (ROOT / 'src/platform/world_bridge.c').read_text()
        declarations = bridge[bridge.index('#define WB_PEERS'):bridge.index('static bool8 Identifier')]
        source = r'''#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <limits.h>
typedef unsigned char bool8;
typedef unsigned char u8;
typedef unsigned short u16;
#define TRUE 1
#define FALSE 0
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
#define A_BUTTON 1
#define B_BUTTON 2
#define DIR_SOUTH 1
#define DIR_NORTH 2
#define DIR_WEST 3
#define DIR_EAST 4
#define MAP_OFFSET 7
#define OBJECT_EVENTS_COUNT 3
struct ObjectEvent {struct {int x,y;} currentCoords; unsigned facingDirection,currentElevation,active,isPlayer;};
static struct ObjectEvent gObjectEvents[3];
static struct {unsigned objectEventId;} gPlayerAvatar;
static struct Save {struct {int mapGroup,mapNum;} location;} save, *gSaveBlock1Ptr=&save;
static int ready=1, owned=1, hidden=1, shown, locks, flushes;
static int activityEnabled, activityOwns, interactions, talkQueued;
static int WorldTravel_OwnsFieldInput(void) { return 0; }
static int WorldActivity_OwnsFieldInput(void) { return activityOwns; }
static int WorldActivity_Interact(const char *peer) {
 assert(!strcmp(peer, "bob")); interactions++;
 if (!activityEnabled) return 0;
 activityOwns=1; return 1;
}
static int WorldActivity_TakeTalkRequest(char peer[25]) {
 if (!talkQueued) return 0;
 strcpy(peer, "bob"); talkQueued=0; return 1;
}
static bool8 Ready(void) {return ready;}
static bool8 Overworld(void) {return 1;}
static bool8 Owned(unsigned i) {return i==0 && owned;}
static bool8 IsFieldMessageBoxHidden(void) {return hidden;}
static void HideFieldMessageBox(void) {hidden=1;}
static void UnlockPlayerFieldControls(void) {locks--;ready=1;}
static void LockPlayerFieldControls(void) {locks++;ready=0;}
static bool8 ShowFieldMessage(const u8 *s) {(void)s; shown++;hidden=0;return 1;}
static bool8 MapCoords(unsigned g,unsigned n,unsigned x,unsigned y) {return g==0 && n==1 && x<30 && y<30;}
static bool8 WorldCatalog_Metatile(unsigned g,unsigned n,unsigned t) {(void)g;(void)n;return t<1024;}
'''+declarations+r'''
static void SendState(void) {sWorld.seq++;}
static void Flush(void) {flushes++;sWorld.outputSize=0;}
'''
        for name in ('Identifier','Decimal','ObjectText','EncodeText','Line','FacingObject','NativeNpcAt',
                     'SyncDialogue','WorldBridge_FilterInput'):
            source += function(bridge, name)
        source += r'''
static int line(const char *s) {char b[512];strcpy(b,s);return Line(b);}
int main(void) {
 sWorld.enabled=sWorld.connected=1;strcpy(sWorld.trainer,"alice");
 gSaveBlock1Ptr->location.mapNum=1;
 gObjectEvents[0].currentCoords.x=17;gObjectEvents[0].currentCoords.y=20;
 gObjectEvents[0].facingDirection=DIR_NORTH;
 gObjectEvents[1].currentCoords.x=17;gObjectEvents[1].currentCoords.y=19;
 strcpy(sWorld.remotes[0].id,"bob");sWorld.remotes[0].object=1;
 assert(line("BEGIN 5"));assert(line("PEER bob 0 1 10 12 1 7 1"));assert(line("END"));
 assert(WorldBridge_FilterInput(A_BUTTON)==0);SyncDialogue();
 assert(flushes==1 && shown==0);assert(strstr(sWorld.output,"MEET 2 bob\n"));
 assert(line("BEGIN 6"));assert(line("MEET 6 alice bob 0 1 10 12 explore"));
 SyncDialogue();assert(shown==0); /* Uncommitted acknowledgement cannot show UI. */
 assert(line("END"));SyncDialogue();assert(shown==1 && locks==1);
 assert(strstr(sWorld.dialogueLiteral,"bob\nLet's explore together!"));
 hidden=1;WorldBridge_FilterInput(0);WorldBridge_FilterInput(A_BUTTON);SyncDialogue();
 assert(locks==0 && !sWorld.dialogueActive);
 SyncDialogue();assert(shown==1); /* Snapshot repeat never reopens. */
 ready=0;WorldBridge_FilterInput(0);assert(WorldBridge_FilterInput(A_BUTTON)==A_BUTTON);
 ready=1;owned=0;WorldBridge_FilterInput(0);assert(WorldBridge_FilterInput(A_BUTTON)==A_BUTTON);
 owned=1;gObjectEvents[2]=gObjectEvents[1];gObjectEvents[2].active=1;
 assert(NativeNpcAt(10,12));
 WorldBridge_FilterInput(0);assert(WorldBridge_FilterInput(A_BUTTON)==A_BUTTON);
 gObjectEvents[2].active=0;
 assert(!NativeNpcAt(10,12));
 owned=1;sWorld.enabled=0;assert(WorldBridge_FilterInput(0xFFFF)==0xFFFF);
 sWorld.enabled=1;
 assert(line("BEGIN 7"));assert(!line("MEET 8 alice bob 0 1 10 12 explore"));
 sWorld.staging=0;
 assert(line("BEGIN 7"));assert(!line("MEET 7 mallory bob 0 1 10 12 explore"));
 sWorld.staging=0;
 assert(line("BEGIN 7"));assert(line("MEET 7 bob alice 0 1 10 13 explore"));
 assert(!line("MEET 7 bob alice 0 1 10 13 explore"));sWorld.staging=0;
 assert(line("BEGIN 7"));assert(line("MEET 7 bob alice 0 1 10 13 explore"));assert(line("END"));
 ready=0;SyncDialogue();assert(shown==1); /* Never hijack a menu/NPC script. */
 ready=1;SyncDialogue();assert(shown==2 && locks==1);
 assert(strstr(sWorld.dialogueLiteral,"bob\nLet's explore together!"));
 assert(line("BEGIN 8"));assert(line("END"));SyncDialogue();assert(!sWorld.dialogueActive && locks==0);
 /* Link unavailable above retains the existing authority-backed greeting. */
 memset(&sWorld,0,sizeof(sWorld));
 sWorld.enabled=sWorld.connected=1;strcpy(sWorld.trainer,"alice");
 strcpy(sWorld.remotes[0].id,"bob");sWorld.remotes[0].object=1;
 ready=hidden=owned=activityEnabled=1;shown=locks=flushes=interactions=0;
 assert(line("BEGIN 1"));assert(line("PEER bob 0 1 10 12 1 7 1"));assert(line("END"));
 WorldBridge_FilterInput(0);assert(WorldBridge_FilterInput(A_BUTTON)==0);SyncDialogue();
 assert(activityOwns && interactions==1 && flushes==0 && shown==0);
 /* Menu A stays in raw gMain. Even a queued authority greeting cannot steal UI. */
 assert(WorldBridge_FilterInput(A_BUTTON)==A_BUTTON);
 assert(line("BEGIN 2"));assert(line("MEET 2 alice bob 0 1 10 12 explore"));
 assert(line("PEER bob 0 1 10 12 1 7 1"));assert(line("END"));
 SyncDialogue();assert(shown==0 && sWorld.shownMeeting==2);
 /* Talk consumes one handoff and sends actual MEET, not another peer menu. */
 activityOwns=0;talkQueued=1;SyncDialogue();
 assert(!talkQueued && interactions==1 && flushes==1);
 assert(strstr(sWorld.output,"MEET 2 bob\n"));
 SyncDialogue();assert(interactions==1 && flushes==1 && shown==0);
 /* A handoff cannot follow a peer that walked away. */
 talkQueued=1;gObjectEvents[1].currentCoords.x++;
 SyncDialogue();assert(flushes==1 && !talkQueued);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='meet-c-', dir=SCRATCH) as tmp:
            c, exe = Path(tmp)/'meet.c', Path(tmp)/'meet'
            c.write_text(source)
            result = subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)], capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result = subprocess.run([str(exe)],capture_output=True,text=True,cwd=tmp)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_meet_is_ordered_durable_private_and_disconnect_clears(self):
        from world.server import WorldServer
        from world.client import WorldClient, admin_request
        with tempfile.TemporaryDirectory(prefix='meet-', dir=SCRATCH) as tmp:
            server = WorldServer(tmp+'/sock', tmp+'/state')
            identities = [server.create_identity(n) for n in ('alice','bob','legacy')]
            server.start()
            clients = []
            try:
                for identity in identities:
                    clients.append(WorldClient(tmp+'/sock', identity['id'], identity['token'],
                                               social=identity['id'] != 'legacy'))
                alice, bob, legacy = clients
                alice.send_state(1, 0,1,10,13,2,7,1,'a'*16,'b'*16)
                bob.send_state(1, 0,1,10,12,1,7,1,'a'*16,'b'*16)
                deadline = time.monotonic()+2
                while time.monotonic()<deadline and len([p for p in server.inspect()['players'] if p.get('ready')])<2:
                    time.sleep(.01)
                alice.meet(2, 'bob')
                for client in (alice,bob):
                    for _ in range(12):
                        snapshot = client.snapshot()
                        if snapshot.get('meeting'): break
                    self.assertEqual(snapshot['meeting']['player'], 'alice')
                    self.assertEqual(snapshot['meeting']['target'], 'bob')
                    self.assertEqual(snapshot['meeting']['signal'], 'explore')
                    self.assertEqual(snapshot['meeting']['seq'], snapshot['revision'])
                self.assertNotIn('MEET', server._snapshot(server.peers['legacy']))
                events = admin_request(tmp+'/sock', dict(command='events_since'))['events']
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]['data']['target'], 'bob')
                self.assertEqual(events[0]['data']['signal'], 'explore')
                self.assertEqual(server._context()['interactions'][0]['kind'], 'trainer')
                # A partner can move/open a menu between snapshots and A. This
                # ordinary race must not evict either authenticated trainer.
                alice.meet(3, 'bob')
                deadline=time.monotonic()+2
                while time.monotonic()<deadline and server.peers['alice']['seq']<3:
                    time.sleep(.01)
                self.assertEqual(server.peers['alice']['seq'],3)
                self.assertFalse(server.peers['alice']['closing'])
                bob.close(); clients.remove(bob)
                for _ in range(12):
                    if alice.snapshot().get('meeting') is None: break
                self.assertIsNone(server.peers['alice'].get('meeting'))
                self.assertFalse(any(Path(i['save_path']).exists() for i in identities))
            finally:
                for client in clients: client.close()
                server.close()
            server = WorldServer(tmp+'/sock', tmp+'/state')
            try:
                self.assertEqual(server._context()['interactions'][0]['target'], 'bob')
            finally:
                server.close()

    def test_meet_rejects_unready_range_map_facing_self_missing_legacy_rate_replay(self):
        from world.server import WorldServer
        # Exercise the real authority method without socket timing to pin rate/order.
        with tempfile.TemporaryDirectory(prefix='meet-', dir=SCRATCH) as tmp:
            server = WorldServer(tmp+'/sock', tmp+'/state')
            try:
                a = dict(id='alice', state=[0,1,10,13,2,7,1], seq=1, social=True)
                b = dict(id='bob', state=[0,1,10,12,1,7,1], seq=1, social=True)
                server.peers = dict(alice=a,bob=b)
                server._broadcast = lambda: None
                for update, target in (({},'alice'), ({},'missing'), ({'social':False},'bob'),
                    ({'state':[0,1,10,12,1,7,0]},'bob'), ({'state':[0,0,10,12,1,7,1]},'bob'),
                    ({'state':[0,1,10,11,1,7,1]},'bob')):
                    old = dict(b); b.update(update)
                    with self.subTest(update=update,target=target), self.assertRaises(ValueError):
                        server._meet(a, ['MEET','2',target])
                    b.clear(); b.update(old)
                a['state'][4] = 1
                with self.assertRaises(ValueError): server._meet(a,['MEET','2','bob'])
                a['state'][4] = 2
                server._meet(a,['MEET','2','bob'])
                with self.assertRaises(ValueError): server._meet(a,['MEET','3','bob'])
                self.assertEqual(a['seq'],2)
                self.assertEqual(server.db.execute("SELECT count(*) FROM events WHERE kind='interaction'").fetchone()[0],1)
            finally:
                server.close()


if __name__ == '__main__':
    unittest.main()
