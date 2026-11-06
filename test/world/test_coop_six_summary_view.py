"""Exercise the private switch view through the battle summary transition."""
from pathlib import Path
import subprocess, tempfile, unittest
from test_save_isolation import function
ROOT = Path(__file__).resolve().parents[2]

class PrivateSummaryView(unittest.TestCase):
 def test_summary_keeps_private_view_and_normal_exit_restores_it(self):
  source = (ROOT/'src/party_menu.c').read_text()
  close = function(source, 'Task_ClosePartyMenuAndSetCB2')
  show = function(source, 'CB2_ShowPokemonSummaryScreen')
  preamble = r'''
#include <assert.h>
#include <stddef.h>
typedef unsigned char u8;
typedef void (*Callback)(void);
#define PARTY_MENU_TYPE_IN_BATTLE 1
#define SUMMARY_MODE_LOCK_MOVES 2
#define SUMMARY_MODE_NORMAL 3
struct { int active; } gPaletteFade;
struct Internal { Callback exitCallback; } internal, *sPartyMenuInternal = &internal;
struct { int menuType, slotId; Callback exitCallback; } gPartyMenu;
int gPlayerParty[6], gPlayerPartyCount=6, active, ended, reordered, mode, freed, destroyed;
Callback next;
int WorldCoop_FullPartyMenuActive(void){return active;}
void WorldCoop_EndFullPartyMenu(void){active=0;ended++;}
void UpdatePartyToFieldOrder(void){reordered++;}
void UpdatePartyToBattleOrder(void){reordered++;}
void SetMainCallback2(Callback c){next=c;}
void ResetSpriteData(void){}
void FreePartyPointers(void){freed++;}
void DestroyTask(u8 id){(void)id;destroyed++;}
void CB2_ReturnToPartyMenuFromSummaryScreen(void){}
void ShowPokemonSummaryScreen(int m,int *p,int slot,int last,Callback cb){
 assert(p==gPlayerParty && slot==2 && last==5 && cb==CB2_ReturnToPartyMenuFromSummaryScreen);mode=m;
}
static void CB2_ShowPokemonSummaryScreen(void);
void battle(void){}
'''
  main = r'''
int main(void){
 gPartyMenu.menuType=PARTY_MENU_TYPE_IN_BATTLE;gPartyMenu.slotId=2;gPartyMenu.exitCallback=battle;
 active=1;internal.exitCallback=CB2_ShowPokemonSummaryScreen;
 Task_ClosePartyMenuAndSetCB2(1);assert(active && !ended && !reordered && next==CB2_ShowPokemonSummaryScreen);
 next();assert(active && mode==SUMMARY_MODE_LOCK_MOVES && !reordered);
 internal.exitCallback=0;Task_ClosePartyMenuAndSetCB2(2);
 assert(!active && ended==1 && !reordered && next==battle && freed==2 && destroyed==2);
 return 0;
}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(preamble+close+show+main)
   q=subprocess.run(['cc','-std=c99','-DPORTABLE','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True)
   self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__': unittest.main()
