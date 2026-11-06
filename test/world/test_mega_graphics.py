"""Exercise the actual graphics adapter with native engine boundaries."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class MegaGraphicsTests(unittest.TestCase):
    def test_form_bitmap_palette_and_vanilla_fallback(self):
        source = (ROOT / 'src/battle_gfx_sfx_util.c').read_text()
        signature = 'static bool8 LoadMegaMonSpriteGfx(struct Pokemon *mon, u8 battler, bool8 back)\n{'
        self.assertTrue(signature in source, 'Missing battle-only Mega sprite adapter')
        start = source.index(signature)
        end = source.index('\n}\n', start) + 3
        fixture = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef u8 bool8;
#define TRUE 1
#define FALSE 0
#define MEGA_FORM_NONE 0
#define MEGA_FORM_COUNT 17
#define MON_DATA_SPECIES 1
#define SPECIES_NONE 0
#define OBJ_PLTT_ID(b) (256+(b)*16)
#define BG_PLTT_ID(b) ((b)*16)
#define PLTT_SIZE_4BPP 32
struct Pokemon {u16 species;bool8 shiny;};
struct MegaFormData {u16 baseSpecies;};
struct {const u32 *front,*back; const u16 *normal,*shiny;} sMegaGraphics[17];
struct {struct {u16 transformSpecies;} battlerData[4];} spriteData,*gBattleSpritesDataPtr=&spriteData;
struct {struct {void *ptr[4];} sprites;} monData,*gMonSpritesGfxPtr=&monData;
u8 gBattleMonForms[4],form;
u16 palette[512];
u8 MegaGame_ActiveForm(u8 b){(void)b;return form;}
u8 GetBattlerPosition(u8 b){return b;}
u32 GetMonData(struct Pokemon *p,int f){(void)f;return p->species;}
bool8 IsMonShiny(struct Pokemon *p){return p->shiny;}
const struct MegaFormData *MegaForm_Get(u8 f){static const struct MegaFormData d={3};return f?&d:0;}
void CpuCopy32(const void *s,void *d,int n){memcpy(d,s,n);}
void LoadPalette(const void *s,int offset,int n){memcpy(palette+offset,s,n);}
'''
        fixture += source[start:end]
        fixture += r'''
int main(void){
 u32 front[512],back[512],dest[2048];u16 normal[16],shiny[16];struct Pokemon mon={3,0};
 for(int i=0;i<512;i++){front[i]=123;back[i]=456;}
 for(int i=0;i<16;i++){normal[i]=77;shiny[i]=88;}
 sMegaGraphics[1].front=front;sMegaGraphics[1].back=back;sMegaGraphics[1].normal=normal;sMegaGraphics[1].shiny=shiny;
 gMonSpritesGfxPtr->sprites.ptr[0]=dest;
 assert(!LoadMegaMonSpriteGfx(&mon,0,0));form=1;
 assert(LoadMegaMonSpriteGfx(&mon,0,0));assert(dest[0]==123 && dest[2047]==123 && palette[256]==77);
 mon.shiny=1;assert(LoadMegaMonSpriteGfx(&mon,0,1));assert(dest[0]==456 && palette[256]==88);
 spriteData.battlerData[0].transformSpecies=99;assert(!LoadMegaMonSpriteGfx(&mon,0,0));
 return 0;
}
'''
        out = ROOT / 'build/rc4-mega'
        out.mkdir(parents=True, exist_ok=True)
        (out / 'graphics_adapter.c').write_text(fixture)
        result = subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(out / 'graphics_adapter.c'), '-o', str(out / 'graphics_adapter')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([str(out / 'graphics_adapter')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
