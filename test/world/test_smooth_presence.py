"""Production bridge motion interpolation against a deterministic engine fixture."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_save_isolation import function
ROOT = Path(__file__).resolve().parents[2]

class SmoothPresence(unittest.TestCase):
    def test_interpolation_keeps_authority_and_handles_changes(self):
        bridge=(ROOT/'src/platform/world_bridge.c').read_text()
        prior=(ROOT/'test/world/test_presence_reconcile.py').read_text()
        fixture=prior.split("        fixture = r'''",1)[1].split("'''",1)[0]
        fixture=fixture.replace('#define UBFIX 1', '''#define UBFIX 1
#define WORLD_SMOOTH_PRESENCE 1
#define DIR_NORTH 2
#define DIR_SOUTH 1
#define DIR_WEST 3
#define DIR_EAST 4
#define OBJ_EVENT_GFX_BRENDAN_NORMAL 0
#define OBJ_EVENT_GFX_BRENDAN_MACH_BIKE 1
#define OBJ_EVENT_GFX_BRENDAN_ACRO_BIKE 2
#define OBJ_EVENT_GFX_MAY_NORMAL 3
#define OBJ_EVENT_GFX_MAY_MACH_BIKE 4
#define OBJ_EVENT_GFX_MAY_ACRO_BIKE 5''')
        fixture=fixture.replace('struct Remote {char id[26];u8 object,sprite,group,num;};',
            'struct Remote {char id[26];u8 object,sprite,group,num;short motionX,motionY;u8 motionDirection;bool8 walking;};')
        fixture=fixture.replace('struct {int inUse,data[8];} gSprites[MAX_SPRITES];',
            'struct Sprite {int inUse,data[8],x2,y2,anim;};struct Sprite gSprites[MAX_SPRITES];')
        fixture += '''\nstatic u8 GetMoveDirectionAnimNum(u8 d){return d+10;}
static void StartSpriteAnimIfDifferent(struct Sprite *s,u8 a){s->anim=a;}\n'''
        fixture += ''.join(function(bridge,name) for name in ('Owned','RemoveRemote','NativeNpcAt','SelectPeers','RemoteWalkAnimationSafe','SyncEngine','AdvanceRemoteMotion'))
        fixture += r'''
int main(void) {
 struct Peer *p=&sWorld.live.peers[0];struct Remote *r=&sWorld.remotes[0];
 unsigned i; sWorld.tilesLive=1;sWorld.live.peerCount=1;strcpy(p->id,"peer");
 p->x=10;p->y=10;p->gfx=7;p->ready=1;p->facing=DIR_EAST;
 graphics[7].paletteSlot=PALSLOT_NPC_1;SyncEngine();if(!Owned(0)) return 1;
 p->x=11;SyncEngine();
 if(gObjectEvents[r->object].currentCoords.x!=18 || r->motionX!=-16 || r->motionY) return 2;
 SyncEngine();if(r->motionX!=-16) return 3; /* reconciliation does not advance time */
 for(i=0;i<8;i++) {AdvanceRemoteMotion(); if(gSprites[r->sprite].x2!=-16+(int)i*2) return 4;}
 if(r->motionX || !r->walking || gSprites[r->sprite].anim!=DIR_EAST+10) return 5;
 AdvanceRemoteMotion();if(gSprites[r->sprite].x2 || r->walking) return 6;
 p->y=11;SyncEngine();AdvanceRemoteMotion();if(gSprites[r->sprite].y2!=-16) return 7;
 p->x=20;SyncEngine();AdvanceRemoteMotion();if(r->motionX||r->motionY||gSprites[r->sprite].x2||gSprites[r->sprite].y2||r->walking) return 8;
 p->x=21;SyncEngine();AdvanceRemoteMotion();p->x=20;SyncEngine();AdvanceRemoteMotion();
 if(r->motionX < -32 || r->motionX > 32) return 9;
 if(RemoteWalkAnimationSafe(8) || !RemoteWalkAnimationSafe(7)) return 11;
 /* Loss of ownership must not modify an engine object which reused the slot. */
 {unsigned slot=r->sprite;gSprites[slot].data[7]=0;gSprites[slot].x2=99;AdvanceRemoteMotion();if(gSprites[slot].x2!=99)return 10;}
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            c,exe=Path(tmp)/'test.c',Path(tmp)/'test';c.write_text(fixture)
            for flags in ([],['-fsanitize=address,undefined','-fno-omit-frame-pointer','-no-pie']):
                r=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',*flags,str(c),'-o',str(exe)],capture_output=True,text=True)
                self.assertEqual(r.returncode,0,r.stderr)
                r=subprocess.run([str(exe)],capture_output=True,text=True)
                self.assertEqual(r.returncode,0,r.stderr or f'exit {r.returncode}')

if __name__=='__main__': unittest.main()
