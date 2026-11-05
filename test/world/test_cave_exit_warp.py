"""Generated cave exit must use the capacity-checked private return."""
from pathlib import Path
from test_save_isolation import function
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class CaveExitWarp(unittest.TestCase):
 def test_cave_routes_through_guard_and_ordinary_warps_stay_unchanged(self):
  src=(ROOT/'src/field_control_avatar.c').read_text()
  code=r'''
#include <assert.h>
typedef unsigned char u8;typedef signed char s8;typedef unsigned short u16;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define WARP_ID_NONE (-1)
struct MapPosition{int x;};struct Header{int x;} gMapHeader;
int cave,canLeave=1,leaves,stored,setups,warps;
s8 GetWarpEventAtMapPosition(struct Header *h,struct MapPosition *p){(void)h;(void)p;return 0;}
int IsArrowWarpMetatileBehavior(u16 b,u8 d){(void)b;(void)d;return 1;}
int GeneratedMap_IsInside(void){return cave;}
int GeneratedMap_Leave(void){leaves++;return canLeave;}
void StoreInitialPlayerAvatarState(void){stored++;}
void SetupWarp(struct Header *h,s8 id,struct MapPosition *p){(void)h;(void)id;(void)p;setups++;}
void DoWarp(void){warps++;}
'''+function(src,'TryArrowWarp')+r'''
int main(void){struct MapPosition p={0};cave=1;canLeave=0;assert(!TryArrowWarp(&p,0,0)&&leaves==1&&!stored&&!setups&&!warps);
 canLeave=1;assert(TryArrowWarp(&p,0,0)&&leaves==2&&!stored&&!setups&&!warps);
 cave=0;assert(TryArrowWarp(&p,0,0)&&stored==1&&setups==1&&warps==1);return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_MAP_READY=1',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
