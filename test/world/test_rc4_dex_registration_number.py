"""Exercise the production registration renderer's numeric selection in C."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class RegistrationNumberTests(unittest.TestCase):
    def test_non_hoenn_expanded_registration_uses_national_number(self):
        source = (ROOT / 'src/pokedex.c').read_text()
        start = source.index('static void PrintMonInfo(u32 num, u32 value, u32 owned, u32 newEntry)\n{')
        end = source.index('\n}\n', start) + 3
        function = source[start:end]
        prelude = r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define SPECIES_NONE 0
#define TRUE 1
#define FONT_NORMAL 1
#define DISPLAY_WIDTH 240
#define STR_CONV_MODE_LEADING_ZEROS 0
static u32 printedNumber, printedDigits;
static const u8 text[] = "";
#define gText_PokedexRegistration text
#define gText_NumberClear01 text
#define sText_TenDashes2 text
#define gText_5MarksPokemon text
#define gText_HTHeight text
#define gText_WTWeight text
#define gText_UnkHeight text
#define gText_UnkWeight text
#define sExpandedPlaceholder_PokedexDescription text
static u8 gSpeciesNames[1300][11];
static struct {u16 height, weight; const u8 *description;} gPokedexEntries[1300];
static void PrintInfoScreenText(const u8 *s, int x, int y) {(void)s;(void)x;(void)y;}
static int GetStringCenterAlignXOffset(int f,const u8 *s,int w) {(void)f;(void)s;(void)w;return 0;}
static u16 NationalToHoennOrder(u32 n) {return n == 1 ? 1 : 0;}
static u16 NationalPokedexNumToSpecies(u32 n) {(void)n;return 0;}
static u16 ExpandedSpecies_FromNationalDexNumber(u32 n) {return n == 790 || n == 808 || n == 999 || n == 1025 ? 440 : 0;}
static u8 *StringCopy(u8 *d,const u8 *s) {strcpy((char *)d,(const char *)s);return d;}
static u8 *ConvertIntToDecimalStringN(u8 *d,u32 n,int mode,int digits) {(void)mode;printedNumber=n;printedDigits=digits;return d;}
static void CopyMonCategoryText(u32 n,u8 *d) {(void)n;d[0]=0;}
static void PrintMonHeight(u16 n,int x,int y) {(void)n;(void)x;(void)y;}
static void PrintMonWeight(u16 n,int x,int y) {(void)n;(void)x;(void)y;}
'''
        main = r'''
int main(void) {
 PrintMonInfo(790,0,1,1);assert(printedNumber==790 && printedDigits==3);
 PrintMonInfo(808,0,1,1);assert(printedNumber==808);
 PrintMonInfo(999,0,1,1);assert(printedNumber==999);
 PrintMonInfo(1025,0,1,1);assert(printedNumber==1025 && printedDigits==4);
 PrintMonInfo(1,0,1,1);assert(printedNumber==1 && printedDigits==3);
 PrintMonInfo(25,1,1,1);assert(printedNumber==25 && printedDigits==3);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='rc4-dex-number-') as directory:
            path = Path(directory)
            (path / 'probe.c').write_text(prelude + function + main)
            result = subprocess.run(['cc', '-std=c99', '-DPORTABLE', str(path / 'probe.c'), '-o', str(path / 'probe')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(path / 'probe')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
