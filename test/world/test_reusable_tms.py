"""Exercise the real successful TM-teaching path with isolated party stubs."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
PRELUDE=r'''
#include <stdint.h>
#include <assert.h>
typedef uint8_t u8; typedef uint16_t u16; typedef int16_t s16;
#define ITEM_TM01 289
#define ITEM_HM01 339
#define FLAG_REUSABLE_TMS 123
#define FRIENDSHIP_EVENT_LEARN_TMHM 1
#define TRUE 1
struct Pokemon {int unused;}; struct Pokemon gPlayerParty[6];
struct {int slotId;s16 data[2];} gPartyMenu;
struct Task {void (*func)(u8);};struct Task gTasks[1];
u16 gSpecialVar_ItemId;int enabled,removed,friendship;
char gStringVar1[32],gStringVar2[32],gStringVar4[32];
const char *gMoveNames[2]={"zero","one"};const char *gText_PkmnLearnedMove3="learned";
static int FlagGet(int x) {(void)x;return enabled;}
static void AdjustFriendship(struct Pokemon *p,int e) {(void)p;(void)e;friendship++;}
static void RemoveBagItem(u16 item,int count) {(void)item;removed+=count;}
static void GetMonNickname(struct Pokemon *p,char *d) {(void)p;(void)d;}
static void StringCopy(char *a,const char *b) {(void)a;(void)b;}
static void StringExpandPlaceholders(char *a,const char *b) {(void)a;(void)b;}
static void DisplayPartyMenuMessage(char *a,int b) {(void)a;(void)b;}
static void ScheduleBgCopyTilemapToVram(int x) {(void)x;}
static void Task_DoLearnedMoveFanfareAfterText(u8 id) {(void)id;}
'''

class ReusableTMTests(unittest.TestCase):
    def test_actual_success_path_preserves_only_enabled_tms(self):
        source=(ROOT/'src/party_menu.c').read_text()
        prefix='static void Task_LearnedMove(u8 taskId)\n{'
        body=source.split(prefix,1)[1].split('\n}\n',1)[0]
        main=r'''
int main(void) {
 gPartyMenu.data[0]=1;gSpecialVar_ItemId=ITEM_TM01;
 enabled=0;Task_LearnedMove(0);assert(removed==1 && friendship==1);
 enabled=1;Task_LearnedMove(0);assert(removed==1 && friendship==2);
 gSpecialVar_ItemId=ITEM_HM01;enabled=0;Task_LearnedMove(0);
 assert(removed==1 && friendship==3);
 gPartyMenu.data[1]=1;gSpecialVar_ItemId=ITEM_TM01;Task_LearnedMove(0);
 assert(removed==1 && friendship==3);
 return 0;
}'''
        with tempfile.TemporaryDirectory() as d:
            c=Path(d)/'t.c';exe=Path(d)/'t';c.write_text(PRELUDE+prefix+body+'\n}\n'+main)
            result=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
    def test_world_menu_has_independent_persistent_toggle(self):
        menu=(ROOT/'src/platform/world_menu.c').read_text()
        self.assertIn('FlagSet(FLAG_REUSABLE_TMS)',menu)
        self.assertIn('FlagClear(FLAG_REUSABLE_TMS)',menu)
        self.assertIn('Reusable TMs: ON',menu)
        self.assertIn('Reusable TMs: OFF',menu)

if __name__=='__main__':unittest.main()
