"""Compile production HUD dispatch. Controlled stubs are not gameplay evidence."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_dexnav_lifecycle import function

ROOT = Path(__file__).resolve().parents[1]

class DexNavHud(unittest.TestCase):
    def test_text_only_hud_never_creates_an_obj_icon(self):
        body = function((ROOT/'src/dexnav.c').read_text(), 'DrawDexNavSearchMonIcon')
        c = r'''
#include <assert.h>
#include <stdint.h>
typedef uint8_t u8; typedef uint16_t u16; typedef u8 bool8;
#define MAX_SPRITES 64
#define SPECIES_ICON_X 28
static bool8 textOnly;
static unsigned icons, badges;
static struct { struct {u8 priority;} oam; }gSprites[MAX_SPRITES];
static struct {u8 ownedIconSpriteId;} search, *sDexNavSearchDataPtr=&search;
static int sOwnedIconTemplate;
static bool8 DexNavNative_TextOnlyHud(void){return textOnly;}
static bool8 DexNavNative_TextBadges(void){return textOnly;}
static u8 GetSearchWindowY(void){return 0;}
static u8 DexNavNative_CreateMonIcon(u16 s,int x,int y,int p){icons++;return 1;}
static u8 DexNavNative_CreateSprite(const int *t,int x,int y,int p){badges++;return 2;}
''' + body + r'''
int main(void){
 u8 dst=0;
 textOnly=1;DrawDexNavSearchMonIcon(1,&dst,1);
 assert(dst==MAX_SPRITES && icons==0 && badges==0);
 textOnly=0;DrawDexNavSearchMonIcon(1,&dst,1);
 assert(dst==1 && icons==1 && badges==1);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='dexnav-hud-') as tmp:
            p=Path(tmp)
            (p/'hud.c').write_text(c)
            result=subprocess.run(['cc','-std=gnu99',str(p/'hud.c'),'-o',str(p/'hud')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(p/'hud')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__ == '__main__':
    unittest.main()
