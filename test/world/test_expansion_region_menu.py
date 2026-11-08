"""Actual Expansion WORLD menu with instrumented field/render backends.

Requires the Expansion source checkout. No pixels or linked gameplay are tested.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest
from test_native_world_menu import PREAMBLE, MAIN

ROOT=Path(__file__).resolve().parents[2]
ENGINE=Path(os.environ.get('EW_EXPANSION_ENGINE',ROOT/'engines/expansion-native'))

class ExpansionRegionMenu(unittest.TestCase):
    def test_region_selection_is_explicit_and_preserves_manual_entry(self):
        menu=(ENGINE/'src/world/world_menu.c').read_text()
        menu=re.sub(r'^#include "[^\"]+"\n','',menu,flags=re.M)
        rally=(ENGINE/'include/platform/world_rally.h').read_text()
        rally=rally[rally.index('#define WORLD_RALLY_ROSTER'):rally.index('/* Main/game thread')]
        widths=re.search(r'gFontSmallLatinGlyphWidths\[\]\s*=\s*(\{.*?\});',(ENGINE/'src/fonts.c').read_text(),re.S).group(1)
        pre=PREAMBLE.replace('int bg,x,y,width,height,palette,base;', 'u8 bg,tilemapLeft,tilemapTop,width,height,paletteNum;u16 baseBlock;')
        pre+=r'''
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
#define COPYWIN_MAP 1
#define WINDOWS_MAX 1
static unsigned char tiles[28*18*32];
static struct {struct WindowTemplate window;unsigned char *tileData;} gWindows[2];
static int gReceivedRemoteLinkPlayers;
int OverworldEncounters_Enabled(void){return 0;}
void OverworldEncounters_Toggle(void){}
const char *OverworldEncounters_UnavailableReason(void){return "Unavailable";}
const char *DexNavNative_UnavailableReason(void){return dexReady?NULL:"Unavailable";}
int WildShuffle_WorldManaged(void){return 0;}
int WorldBridge_RulesPending(void){return 0;}
void LoadBgTiles(unsigned bg,const void *data,unsigned size,unsigned base){(void)bg;(void)data;assert(base+size/32<=768);}
void WriteSequenceToBgTilemapBuffer(unsigned bg,unsigned base,unsigned x,unsigned y,unsigned w,unsigned h,unsigned pal,unsigned delta){(void)bg;(void)base;(void)x;(void)y;(void)w;(void)h;(void)pal;(void)delta;}
#define WORLD_REGION_PAGE 4
struct WorldRegion {char place[42],label[21];};
static struct WorldRegion places[4];static unsigned count,next,requests,selections;static int regions;
int WorldBridge_RegionsAvailable(void){return regions;}
unsigned WorldBridge_RegionCount(void){return count;}
unsigned WorldBridge_RegionNext(void){return next;}
const struct WorldRegion *WorldBridge_Region(unsigned i){return i<count?&places[i]:NULL;}
const char *WorldBridge_RegionStatus(void){return NULL;}
int WorldBridge_RequestRegions(unsigned offset){requests++;assert(offset==0||offset==4);return 1;}
int WorldBridge_SelectRegion(const char *place){assert(!strcmp(place,places[0].place));selections++;return 1;}
'''+rally+'\n#include "constants/characters.h"\n'+r'''
static struct WorldRallySnapshot live;
int WorldRally_GetSnapshot(struct WorldRallySnapshot *out){*out=live;return rallyOnline;}
static const unsigned widths[]='''+widths+r''';
unsigned GetStringWidth(unsigned font,const u8 *text,int spacing){unsigned width=0;(void)font;(void)spacing;for(;*text!=EOS;text++){assert(*text<ARRAY_COUNT(widths));width+=widths[*text];}return width;}
void AddTextPrinterParameterized(unsigned window,unsigned font,const u8 *text,unsigned x,unsigned y,int speed,void *cb){(void)window;(void)speed;(void)cb;assert(x+GetStringWidth(font,text,0)<=224);assert(y+12<=144);}
'''
        helpers=MAIN[:MAIN.index('static void CheckHelpFits')]
        main=r'''
int main(void){struct Row rows[ACTION_COUNT];unsigned n;
gWindows[0].window.bg=255;gWindows[1].tileData=tiles;
Reset();regions=1;enabled=fresh=1;count=4;next=4;strcpy(places[0].place,"area:12345678-1234-1234-1234-123456789abc");
for(unsigned i=0;i<4;i++)snprintf(places[i].label,21,"Place %u",i);
Open();DrawAction(GEN_CAVE);assert(ScreenHas("Explore world places"));Press(A_BUTTON);assert(sMenu.state==REGION_MENU&&requests==1);
n=Rows(rows,&live,1);assert(n==7&&rows[n-1].action==BACK);
DrawAction(REGION_0);Press(A_BUTTON);assert(sMenu.state==DISPATCH&&!locked&&!frozen&&!selections&&!calls);
WorldMenu_Update();WorldMenu_Update();WorldMenu_Update();assert(selections==1&&!calls);
canEnter=1;Open();Press(A_BUTTON);assert(sMenu.state==REGION_MENU);DrawAction(GEN_ENTER);Press(A_BUTTON);
WorldMenu_Update();WorldMenu_Update();WorldMenu_Update();assert(calls==1);
Open();Press(A_BUTTON);DrawAction(REGION_NEXT);Press(A_BUTTON);assert(requests==4);
Press(B_BUTTON);assert(sMenu.state==FEATURES);Press(B_BUTTON);assert(sMenu.state==CLOSED&&!locked);
inside=1;Open();n=Rows(rows,&live,1);assert(n==2&&rows[0].action==GEN_CAVE);Press(A_BUTTON);WorldMenu_Update();WorldMenu_Update();assert(calls==2);
return 0;}
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.c').write_text(pre+menu+helpers+main)
            result=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_MAP_READY=1','-DGENERATED_WORLD_REGIONS=1','-iquote',str(ENGINE/'include'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(p/'test')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
