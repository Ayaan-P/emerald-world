"""Narrow client checks: no game binary, SDL, SDK or human sessions."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

from test_save_isolation import function
ROOT = Path(__file__).resolve().parents[2]


class SharedClient(unittest.TestCase):
    def test_disconnect_preserves_local_world_until_explicit_shutdown(self):
        from world.session import DesktopSession
        with tempfile.TemporaryDirectory() as tmp:
            session = DesktopSession(Path(tmp))
            server, broker = Mock(), Mock()
            session.state = Path(tmp)/'hoenn'
            session.server, session.broker = server, broker
            session.disconnect()
            server.close.assert_not_called()
            broker.close.assert_not_called()
            self.assertIsNone(session.state)
            self.assertEqual(session.hosted_worlds(), ['hoenn'])
            session.shutdown_world('hoenn')
            server.close.assert_called_once()
            broker.close.assert_called_once()
            self.assertEqual(session.hosted_worlds(), [])

    def test_remote_disconnect_only_closes_client_broker(self):
        from world.session import DesktopSession, SessionError
        with tempfile.TemporaryDirectory() as tmp:
            session = DesktopSession(Path(tmp))
            broker = Mock()
            session.state, session.broker = Path(tmp)/'remote', broker
            session.remote_trainer = 'alice'
            with self.assertRaises(SessionError):
                session.shutdown_world('remote')
            broker.close.assert_not_called()
            session.disconnect()
            broker.close.assert_called_once()
            self.assertEqual(session.hosted_worlds(), [])

    def test_local_host_can_rejoin_after_disconnect_without_replacing_authority(self):
        from world.session import DesktopSession
        with tempfile.TemporaryDirectory() as tmp:
            session = DesktopSession(Path(tmp))
            session.create_world('hoenn')
            session.host('hoenn')
            original = session.server
            try:
                session.disconnect()
                self.assertTrue((Path(tmp)/'hoenn/transport/world.sock').is_socket())
                session.host('hoenn')
                self.assertIs(session.server, original)
                self.assertTrue(session.connection_status()['connected'])
                session.shutdown_world('hoenn')
                self.assertFalse((Path(tmp)/'hoenn/transport/world.sock').exists())
            finally:
                session.close()

    def test_launcher_roster_reports_busy_humans_without_sprites(self):
        import json
        from world.session import DesktopSession
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = DesktopSession(root)
            session.state = root/'remote'
            session.connection_status = Mock(return_value={'connected': True, 'remote': True})
            session.gm_status = Mock(return_value={})
            telemetry = root/'public.json'
            telemetry.write_text(json.dumps({'trainer': 'alice', 'frame': 1, 'revision': 1,
                'connected': True, 'peers': [], 'roster': [
                    {'trainer': 'bob', 'nearby': True, 'ready': False, 'rendered': False,
                     'party': 'PRIVATE-MUST-NOT-DISPLAY'}]}))
            child = Mock()
            child.poll.return_value = None
            session.games['alice'] = (child, {'profile': root, 'telemetry': telemetry})
            output = session.poll()
            self.assertIn('bob (busy, not inviteable, roster only', output)
            self.assertNotIn('PRIVATE-MUST-NOT-DISPLAY', output)

    def test_busy_presence_never_refreshes_anchor_from_scripts_or_native_pool(self):
        source = (ROOT/'src/platform/world_bridge.c').read_text()
        fixture = r'''
#include <string.h>
#include <stdio.h>
typedef unsigned char bool8;
#define TRUE 1
#define FALSE 0
#define MAP_OFFSET 7
struct Peer {unsigned group,num,x,y,facing,gfx;};
struct {struct Peer field;bool8 fieldKnown,menuAnchor;} sWorld;
struct {int active; } gPaletteFade;
struct ObjectEvent {struct {int x,y;} currentCoords;unsigned facingDirection,graphicsId;} gObjectEvents[16];
struct {unsigned objectEventId;} gPlayerAvatar;
struct Save {struct {int mapGroup,mapNum;} location;} save,*gSaveBlock1Ptr=&save;
static void CB1_Overworld(void) {}
struct {int inBattle;void (*callback1)(void);} gMain;
static int overworld=1,script,ready=1,start,activity;
static int Overworld(void) {return overworld;}
static int PresenceReady(void) {return ready;}
static int ScriptContext_IsEnabled(void) {return script;}
static void Task_ShowStartMenu(void) {}
static int FuncIsActiveTask(void (*fn)(void)) {(void)fn;return start;}
static int WorldActivity_OwnsFieldInput(void) {return activity;}
static const char *WorldActivity_Phase(void) {return activity==2 ? "menu" : "native";}
static int WorldActivity_IsEncounterPending(void) {return 0;}
static int MapCoords(unsigned g,unsigned n,unsigned x,unsigned y) {return g<2&&n<2&&x<100&&y<100;}
'''
        fixture += function(source, 'UpdateFieldPresence')
        fixture += r'''
int main(void) {
 gMain.callback1=CB1_Overworld;gObjectEvents[0].currentCoords.x=17;gObjectEvents[0].currentCoords.y=19;
 UpdateFieldPresence();if(!sWorld.fieldKnown || sWorld.field.x!=10) return 1;
 ready=0;activity=1;gObjectEvents[0].currentCoords.x=80;UpdateFieldPresence();
 if(!sWorld.fieldKnown || sWorld.field.x!=10) return 2;
 overworld=0;gMain.callback1=NULL;gMain.inBattle=1;script=1;UpdateFieldPresence();
 if(!sWorld.fieldKnown || sWorld.field.x!=10) return 3;
 save.location.mapNum=1;UpdateFieldPresence();if(sWorld.fieldKnown) return 4;
 save.location.mapNum=0;activity=0;gMain.callback1=CB1_Overworld;gMain.inBattle=0;overworld=1;script=0;ready=1;
 gObjectEvents[0].currentCoords.x=17;UpdateFieldPresence();
 ready=0;script=1;UpdateFieldPresence();if(sWorld.fieldKnown) return 5;
 script=0;activity=1;UpdateFieldPresence();if(sWorld.fieldKnown) return 6;
 activity=0;ready=1;UpdateFieldPresence();ready=0;gPaletteFade.active=1;
 UpdateFieldPresence();if(sWorld.fieldKnown) return 7;
 gPaletteFade.active=0;ready=1;UpdateFieldPresence();ready=0;start=1;
 UpdateFieldPresence();if(!sWorld.fieldKnown || !sWorld.menuAnchor) return 8;
 start=0;overworld=0;gObjectEvents[0].currentCoords.x=90;UpdateFieldPresence();
 if(!sWorld.fieldKnown || sWorld.field.x!=10) return 9;
 script=1;UpdateFieldPresence();if(sWorld.fieldKnown) return 10;
 script=0;overworld=1;ready=1;UpdateFieldPresence();ready=0;script=1;activity=2;
 UpdateFieldPresence();if(sWorld.fieldKnown) return 11;
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'presence.c'
            path.write_text(fixture)
            subprocess.run(['cc', '-std=gnu11', '-Wall', '-Werror', str(path), '-o', str(Path(tmp)/'check')], check=True)
            subprocess.run([str(Path(tmp)/'check')], check=True)


if __name__ == '__main__':
    unittest.main()
