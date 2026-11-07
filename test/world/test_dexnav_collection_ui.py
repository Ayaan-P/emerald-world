"""Compile the actual native-source candidate, without a game or sockets.

The patch carries enough unchanged context to test its real getter and input
handler too. EW_RC7_ENGINE additionally checks these bytes against an applied
Expansion checkout. Fixtures do not establish rendered/native acceptance.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from test.world.test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]
HANDOFF = ROOT / 'docs/attempt-handoffs/rc7'


def sources():
    result, path = {}, None
    for line in (HANDOFF / 'native-collecting-ui.patch').read_text().splitlines():
        if line.startswith('+++ b/'):
            path = line[6:]
            result[path] = []
        elif path and line.startswith((' ', '+')):
            result[path].append(line[1:])
        elif path and line == '':
            result[path].append('')
    return {path: '\n'.join(lines) for path, lines in result.items()}


PREAMBLE = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint8_t bool8;
#define TRUE 1
#define FALSE 0
enum Species { SPECIES_NONE };
enum { ROW_WATER, ROW_LAND_TOP, ROW_LAND_BOT, ROW_HIDDEN, ROWS_COUNT };
#define COL_WATER_COUNT 5
#define COL_LAND_COUNT 6
#define COL_HIDDEN_COUNT 3
#define COL_WATER_MAX 4
#define COL_LAND_MAX 5
#define COL_HIDDEN_MAX 2
#define FLAG_GET_SEEN 1
#define FLAG_GET_CAUGHT 2
#define DN_FLAG_DETECTOR_MODE 3
#define FLAG_SYS_POKEDEX_GET 4
#define DN_VAR_SPECIES 7
#define DEXNAV_MASK_SPECIES 0x3fff
#define A_BUTTON 1
#define B_BUTTON 2
#define L_BUTTON 4
#define R_BUTTON 8
#define DPAD_UP 16
#define DPAD_DOWN 32
#define DPAD_LEFT 64
#define DPAD_RIGHT 128
#define JOY_NEW(key) (gMain.newKeys & (key))
#define SE_POKENAV_OFF 1
#define SE_RG_BAG_CURSOR 2
#define SE_FAILURE 3
#define SE_DEX_SEARCH 4
#define RGB_BLACK 0
#define WINDOW_REGISTERED 0
#define TEXT_COLOR_TRANSPARENT 0
#define FONT_SMALL 0
#define TEXT_SKIP_DRAW 0
#define PIXEL_FILL(x) (x)
struct Task {void (*func)(u8);};
struct Task gTasks[1];
struct {unsigned newKeys;int inBattle;} gMain;
struct Gui {enum Species waterSpecies[5],landSpecies[12],hiddenSpecies[3];u8 cursorRow,cursorCol,environment;} gui, *sDexNavUiDataPtr=&gui;
static unsigned seen[128],caught[128],detector,pokedex,registered,updates,sound,cry,fade,searchable,notice;
static int sePlaying;
static unsigned gSpecialVar_0x8000,gSpecialVar_0x8001,gSpecialVar_0x8002;
static const u8 sFontColor_White[]={0},sText_DexNav_NoKnownUncaught[]={0};
unsigned SpeciesToNationalPokedexNum(enum Species species) {assert((unsigned)species<128);return species==102?2:(unsigned)species;}
unsigned GetSetPokedexFlag(unsigned dex,unsigned action) {assert(dex<128);assert(action==FLAG_GET_SEEN||action==FLAG_GET_CAUGHT);return action==FLAG_GET_SEEN?seen[dex]:caught[dex];}
unsigned FlagGet(unsigned flag) {assert(flag==DN_FLAG_DETECTOR_MODE||flag==FLAG_SYS_POKEDEX_GET);return flag==DN_FLAG_DETECTOR_MODE?detector:pokedex;}
unsigned VarGet(unsigned var) {assert(var==DN_VAR_SPECIES);return registered;}
void VarSet(unsigned var,unsigned value) {assert(var==DN_VAR_SPECIES);registered=value;}
void UpdateCursorPosition(void) {updates++;gui.environment=gui.cursorRow==ROW_WATER?1:gui.cursorRow==ROW_HIDDEN?2:0;}
int IsSEPlaying(void) {return sePlaying;}
void PlaySE(unsigned value) {sound=value;}
void PlayCry_Script(enum Species species,unsigned delay) {(void)delay;cry=species;}
void BeginNormalPaletteFade(unsigned a,int b,int c,int d,int e) {(void)a;(void)b;(void)c;(void)d;(void)e;fade++;}
void Task_DexNavFadeAndExit(u8 task) {(void)task;}
void Task_DexNavExitAndSearch(u8 task) {(void)task;}
void PrintSearchableSpecies(enum Species species) {searchable=species;}
void FillWindowPixelBuffer(unsigned a,unsigned b) {(void)a;(void)b;}
void AddTextPrinterParameterized3(unsigned a,unsigned b,unsigned c,unsigned d,const u8 *e,unsigned f,const u8 *g) {(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;assert(g==sText_DexNav_NoKnownUncaught);notice++;}
void PrintMapName(void) {}
static void reset(void) {
 memset(&gui,0,sizeof(gui));memset(seen,0,sizeof(seen));memset(caught,0,sizeof(caught));
 memset(gTasks,0,sizeof(gTasks));memset(&gMain,0,sizeof(gMain));
 detector=0;pokedex=1;registered=91;updates=sound=cry=fade=searchable=notice=0;sePlaying=0;
 gSpecialVar_0x8000=77;gSpecialVar_0x8001=88;gSpecialVar_0x8002=99;
}
static void press(unsigned keys) {gMain.newKeys=keys;Task_DexNavMain(0);gMain.newKeys=0;}
'''


CASES = r'''
int main(void) {
 unsigned i,mask;struct Gui before;
 reset();gui.cursorRow=ROW_LAND_TOP;gui.landSpecies[0]=1;seen[1]=caught[1]=1;
 gui.landSpecies[8]=2;seen[2]=1;gui.waterSpecies[0]=3; /* unseen */
 gui.hiddenSpecies[0]=4;seen[4]=1; /* detector locked */
 press(L_BUTTON);assert(gui.cursorRow==ROW_LAND_BOT&&gui.cursorCol==2&&gui.environment==0);
 assert(registered==91&&searchable==91&&updates==1&&sound==SE_RG_BAG_CURSOR);
 assert(!cry&&!fade&&gSpecialVar_0x8000==77&&gSpecialVar_0x8001==88&&gSpecialVar_0x8002==99);
 assert(!caught[2]&&!caught[3]&&!caught[4]);
 press(L_BUTTON);assert(gui.cursorRow==ROW_LAND_BOT&&gui.cursorCol==2); /* one eligible wraps */
 detector=1;press(L_BUTTON);assert(gui.cursorRow==ROW_HIDDEN&&gui.cursorCol==0&&gui.environment==2);
 seen[3]=1;press(L_BUTTON);assert(gui.cursorRow==ROW_WATER&&gui.cursorCol==0&&gui.environment==1);
 caught[2]=caught[3]=caught[4]=1;before=gui;i=updates;press(L_BUTTON);
 assert(!memcmp(&before,&gui,sizeof(gui))&&updates==i&&notice==1&&sound==SE_FAILURE&&registered==91);
 reset();before=gui;press(L_BUTTON);assert(!memcmp(&before,&gui,sizeof(gui))&&notice==1);
 reset();gui.cursorRow=ROWS_COUNT;assert(!DexNavSelectNextUncaught());
 gui.cursorRow=ROW_WATER;gui.cursorCol=5;assert(!DexNavSelectNextUncaught());
 reset();gui.landSpecies[0]=102;seen[2]=caught[2]=1; /* same national species, alternate form */
 assert(!DexNavSelectNextUncaught());caught[2]=0;assert(DexNavSelectNextUncaught());
 assert(gui.cursorRow==ROW_LAND_TOP&&gui.cursorCol==0);
 reset();gui.landSpecies[0]=2;seen[2]=1;sePlaying=1;press(L_BUTTON);assert(updates==0);sePlaying=0;
 press(B_BUTTON|L_BUTTON);assert(gTasks[0].func==Task_DexNavFadeAndExit&&fade==1&&updates==0);
 reset();gui.cursorRow=ROW_LAND_TOP;gui.landSpecies[0]=2;seen[2]=1;
 press(R_BUTTON);assert(registered==2&&cry==2&&!fade); /* unchanged register action */
 press(A_BUTTON);assert(gSpecialVar_0x8000==2&&gSpecialVar_0x8001==0&&gSpecialVar_0x8002==0);
 assert(gTasks[0].func==Task_DexNavExitAndSearch&&fade==1); /* search remains explicit */
 reset();gui.cursorRow=ROW_LAND_TOP;gui.landSpecies[0]=2; /* unseen remains unsearchable */
 press(A_BUTTON);assert(!fade&&gSpecialVar_0x8000==77&&sound==SE_FAILURE);
 press(R_BUTTON);assert(registered==91&&!cry);
 /* Every cursor position and a broad set of trainer-owned collection states.
  * L must be bounded, preserve encounter arrays and never write a dex flag. */
 for(mask=0;mask<512;mask++) for(i=0;i<20;i++) {
  unsigned row=i<5?0:i<11?1:i<17?2:3,col=i-(row==0?0:row==1?5:row==2?11:17),j;
  reset();detector=mask&1;gui.cursorRow=row;gui.cursorCol=col;
  for(j=0;j<5;j++)gui.waterSpecies[j]=j+1;
  for(j=0;j<12;j++)gui.landSpecies[j]=j+6;
  for(j=0;j<3;j++)gui.hiddenSpecies[j]=j+18;
  for(j=1;j<=20;j++){seen[j]=(mask>>(j%9))&1;caught[j]=(mask>>((j+3)%9))&1;}
  before=gui;press(L_BUTTON);
  assert(!memcmp(before.waterSpecies,gui.waterSpecies,sizeof(gui.waterSpecies)));
  assert(!memcmp(before.landSpecies,gui.landSpecies,sizeof(gui.landSpecies)));
  assert(!memcmp(before.hiddenSpecies,gui.hiddenSpecies,sizeof(gui.hiddenSpecies)));
  assert(registered==91&&!fade&&!cry&&gSpecialVar_0x8000==77);
  if(updates){unsigned species=DexNavGetSpecies();assert(species&&seen[species]&&!caught[species]);}
  else assert(!memcmp(&before,&gui,sizeof(gui)));
 }
 puts("DexNav collection/input assertions completed");return 0;
}
'''


class DexNavCollectionUI(unittest.TestCase):
    def compile_run(self, source, flags=()):
        for compiler in ('cc', 'clang'):
            if not shutil.which(compiler):
                continue
            with self.subTest(compiler=compiler), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'fixture.c').write_text(source)
                result = subprocess.run([compiler, '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                                         '-DPORTABLE', '-fsanitize=undefined', '-fno-sanitize-recover=all',
                                         *flags, str(root / 'fixture.c'), '-o', str(root / 'fixture')], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                result = subprocess.run([str(root / 'fixture')], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_real_getter_navigation_and_input_preserve_collection_privacy(self):
        source = sources()['src/dexnav.c']
        code = '\n'.join(function(source, name) for name in ('DexNavGetSpecies', 'DexNavSelectNextUncaught', 'Task_DexNavMain'))
        # The input fixture calls the production handler, not a reimplemented shortcut.
        pre = PREAMBLE.replace('static void press(unsigned keys)', 'static void Task_DexNavMain(u8 taskId);\nstatic void press(unsigned keys)')
        self.compile_run(pre + code + CASES)

    def test_exact_unavailable_reasons_preserve_existing_eligibility(self):
        source = sources()['src/world/dexnav_native.c']
        code = '\n'.join(function(source, name) for name in ('DexNavNative_UnavailableReason', 'DexNavNative_Available'))
        self.compile_run(r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned u32;typedef int bool8;
#define DEXNAV_ENABLED 1
#define FLAG_SYS_POKEDEX_GET 1
#define PYRAMID_LOCATION_NONE 0
#define MAPSEC_BATTLE_FRONTIER 9
#define PARTY_SIZE 6
#define MON_DATA_SPECIES 0
#define MON_DATA_IS_EGG 1
#define MON_DATA_HP 2
static struct {unsigned data[3];} gPlayerParty[6];
static struct {int inBattle;} gMain;
static struct {int regionMapSectionId;} gMapHeader;
static int dex,safari,pike,pyramid,link,native,generated;
int FlagGet(int f){(void)f;return dex;}int GetSafariZoneFlag(void){return safari;}
int InBattlePike(void){return pike;}int CurrentBattlePyramidLocation(void){return pyramid;}
int IsOverworldLinkActive(void){return link;}int NativeLink_IsActive(void){return native;}
void *GeneratedMap_Wildlife(void){return generated?&generated:NULL;}
unsigned GetMonData(const void *p,unsigned field){return ((const unsigned *)p)[field];}
''' + code + r'''
int main(void){
 unsigned mask;const char *reason;
 for(mask=0;mask<4096;mask++){
  dex=mask&1;safari=(mask>>1)&1;pike=(mask>>2)&1;pyramid=(mask>>3)&1;
  gMapHeader.regionMapSectionId=((mask>>4)&1)?MAPSEC_BATTLE_FRONTIER:0;
  link=(mask>>5)&1;native=(mask>>6)&1;gMain.inBattle=(mask>>7)&1;generated=(mask>>8)&1;
  gPlayerParty[5].data[0]=(mask>>9)&1;gPlayerParty[5].data[1]=(mask>>10)&1;gPlayerParty[5].data[2]=(mask>>11)&1;
  reason=DexNavNative_UnavailableReason();
  assert(DexNavNative_Available()==(reason==NULL));
  assert((reason==NULL)==(dex&&!safari&&!pike&&!pyramid&&!gMapHeader.regionMapSectionId&&!link&&!native&&!gMain.inBattle&&!generated&&gPlayerParty[5].data[0]&&!gPlayerParty[5].data[1]&&gPlayerParty[5].data[2]));
  if(!dex)assert(strstr(reason,"Pokedex"));
  else if(safari)assert(strstr(reason,"Safari"));
  else if(generated&&!pike&&!pyramid&&!gMapHeader.regionMapSectionId&&!link&&!native&&!gMain.inBattle)assert(strstr(reason,"generated-area"));
 }
 puts("DexNav availability assertions completed");return 0;
}
''')

    def test_source_handoff_extends_exact_player_ui_without_changing_release_pin(self):
        manifest = json.loads((HANDOFF / 'collecting-ui-source-manifest.json').read_text())
        base = json.loads((HANDOFF / 'player-ui-source-manifest.json').read_text())
        self.assertEqual(manifest['base_tree'], base['result_tree'])
        self.assertEqual(manifest['base_engine_commit'], base['base_engine_commit'])
        self.assertEqual(manifest['ordered_patches'], base['ordered_patches'] + [manifest['patch']])
        self.assertEqual(hashlib.sha256((HANDOFF / manifest['patch']).read_bytes()).hexdigest(), manifest['patch_sha256'])
        self.assertEqual(set(sources()), {item['path'] for item in manifest['files']})
        if os.environ.get('EW_RC7_ENGINE'):
            engine = Path(os.environ['EW_RC7_ENGINE'])
            for item in manifest['files']:
                self.assertEqual(hashlib.sha256((engine / item['path']).read_bytes()).hexdigest(), item['sha256'])
            for path, names in {'src/dexnav.c': ('DexNavGetSpecies', 'DexNavSelectNextUncaught', 'Task_DexNavMain'),
                                'src/world/dexnav_native.c': ('DexNavNative_UnavailableReason', 'DexNavNative_Available')}.items():
                for name in names:
                    self.assertEqual(function(sources()[path], name), function((engine / path).read_text(), name))

    def test_new_action_is_native_only_and_does_not_apply_gameplay_options(self):
        source = sources()['src/dexnav.c']
        self.assertIn('#ifdef PORTABLE\n/* Navigate only', source)
        self.assertIn('#ifdef PORTABLE\n    else if (JOY_NEW(L_BUTTON))', source)
        getter = function(source, 'DexNavGetSpecies')
        self.assertIn('FLAG_GET_SEEN', getter)
        self.assertIn('DN_FLAG_DETECTOR_MODE', getter)
        shortcut = function(source, 'DexNavSelectNextUncaught')
        for forbidden in ('VarSet', 'FlagSet', 'FLAG_SET', 'CreateMon', 'Random(', 'SetMonData', 'dexNavChain', 'dexNavSearchLevels'):
            self.assertNotIn(forbidden, shortcut)
        self.assertIn('DexNavNative_UnavailableReason()', sources()['src/world/world_menu.c'])

    def test_header_shortcut_and_registration_have_separate_font_width_budget(self):
        source = sources()['src/dexnav.c']
        self.assertIn('sText_DexNav_NextUncaught, 208)', function(source, 'PrintMapName'))
        self.assertIn('const u8 font = FONT_SMALL;', function(source, 'PrintSearchableSpecies'))
        # The native L icon is 16px. Common Latin glyph widths match the source
        # table in both cohorts; no bitmap or full-screen render is claimed.
        raw = re.search(r'gFontSmallLatinGlyphWidths\[\]\s*=\s*\{(.*?)\};', (ROOT / 'src/fonts.c').read_text(), re.S).group(1)
        raw = re.sub(r'/\*.*?\*/|//[^\n]*', '', raw, flags=re.S)
        widths = [int(n, 0) for n in re.findall(r'0x[0-9a-fA-F]+|\d+', raw)]
        chars = {match.group(1): int(match.group(2), 16) for match in re.finditer(r"^'(.)'\s*=\s*([0-9A-F]{2})\s*$", (ROOT / 'charmap.txt').read_text(), re.M)}
        width = lambda text: sum(widths[chars[char]] for char in text)
        right = 16 + width(' UNCAUGHT')
        for left in ('R TO REGISTER!', 'No known uncaught', 'Search ' + 'W' * 12):
            self.assertLess(width(left) + 8 + right, 208)


if __name__ == '__main__':
    unittest.main()
