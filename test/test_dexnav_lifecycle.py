"""Actual-C DexNav lifecycle regression; fixture stubs are not native gameplay."""
from pathlib import Path
import re,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
def function(s,name):
 m=re.search(r'^(?:static )?[\w *]+\b'+name+r'\([^;\n]*\)\n\{',s,re.M)
 if not m:raise AssertionError(name+' missing')
 i=s.index('{',m.start())+1;depth=1
 while depth:depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
class DexNavLifecycle(unittest.TestCase):
 def test_intentional_target_does_not_run_ordinary_encounter_substitution(self):
  source=(ROOT/'src/wild_encounter.c').read_text()
  body=function(source,'WildEncounter_CreateDexNavMon')
  ordinary_body=function(source,'CreateWildMon')
  c=r'''
#include <assert.h>
#include <stdint.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;
static int gEnemyParty[1];static unsigned ordinary,exact;static u16 finalSpecies;
static unsigned CalculateDexNavShinyRolls(void){return 0;}
static struct {struct {u8 mapGroup,mapNum;}location;}save,*gSaveBlock1Ptr=&save;
static u16 ExpandedSpecies_ResolveEncounter(u16 s,u8 group,u8 num){(void)s;(void)group;(void)num;ordinary++;return 999;}
static unsigned rngCalls;static u16 roll;
static u16 Random(void){rngCalls++;return roll;}
static void CreateWildMonExact(u16 s,u8 l){(void)l;exact++;finalSpecies=s;}
static int IsMonShiny(int *m){(void)m;return 0;}
''' + ordinary_body + body + r'''
int main(void){
 WildEncounter_CreateDexNavMon(286,3);assert(finalSpecies==286 && exact==1 && ordinary==0 && rngCalls==0);
 roll=0;CreateWildMon(286,3);assert(finalSpecies==286 && exact==2 && ordinary==1 && rngCalls==1);
 roll=1;CreateWildMon(286,3);assert(finalSpecies==999 && exact==3 && ordinary==2 && rngCalls==2);
 return 0;
}
'''
  with tempfile.TemporaryDirectory(prefix='dexnav-target-')as tmp:
   p=Path(tmp);(p/'test.c').write_text(c)
   subprocess.run(['cc','-std=gnu99',str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True,text=True)
   result=subprocess.run([str(p/'test')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
 def test_real_latch_rejects_unrelated_battle_and_is_consumed_once(self):
  s=(ROOT/'src/platform/dexnav_native.c').read_text()
  names=['DexNavNative_SetBattleOwner','DexNavNative_OwnsWildMon','DexNavNative_AbandonBattle','DexNavNative_PrepareNativeActivity','DexNavNative_CancelForOtherBattle','DexNavNative_BattleFinished']
  bodies='\n'.join(function(s,n)for n in names if re.search(r'\b'+n+r'\([^;]*\)\n\{',s))
  c=r'''
#include <assert.h>
#include <stdint.h>
#include "constants/species.h"
#include "constants/battle.h"
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef u8 bool8;
#define FALSE 0
#define TRUE 1
#define MON_DATA_SPECIES 0
#define MON_DATA_PERSONALITY 1
struct Mon { u16 species; u32 personality; } gEnemyParty[1];
static u16 sBattleOwner, gDexNavSpecies; static u32 sBattlePersonality, gBattleTypeFlags;
static struct { u8 dexNavChain, dexNavSearchLevels[NUM_SPECIES]; bool8 searching; } gDexNavNativeState;
static unsigned freed,persisted;
static u32 GetMonData(struct Mon *m,unsigned f) { return f==MON_DATA_SPECIES ? m->species : m->personality; }
static void EndDexNavSearch(void) { if(gDexNavNativeState.searching)freed++;gDexNavNativeState.searching=FALSE; }
static void IncrementDexNavChain(void) { gDexNavNativeState.dexNavChain++; }
static void DexNavNative_Persist(void) { persisted++; }
'''+bodies+r'''
int main(void) {
 assert(gBattleTypeFlags==0);
 gEnemyParty[0]=(struct Mon){7,100};
 DexNavNative_SetBattleOwner(7);
 gEnemyParty[0].personality=101;
 DexNavNative_CancelForOtherBattle();
 DexNavNative_BattleFinished(B_OUTCOME_WON);
 assert(!gDexNavNativeState.dexNavSearchLevels[7] && !persisted);
 gEnemyParty[0].personality=100;
 DexNavNative_SetBattleOwner(7);
 DexNavNative_CancelForOtherBattle();
 assert(DexNavNative_OwnsWildMon());
 DexNavNative_BattleFinished(B_OUTCOME_WON);
 DexNavNative_BattleFinished(B_OUTCOME_WON);
 assert(gDexNavNativeState.dexNavSearchLevels[7]==1 && persisted==1);
 gDexNavNativeState.searching=TRUE;
 DexNavNative_CancelForOtherBattle();
 assert(!gDexNavNativeState.searching && freed==1);
 return 0;
}
'''
  with tempfile.TemporaryDirectory(prefix='ew-dexnav-lifecycle-')as tmp:
   p=Path(tmp);(p/'test.c').write_text(c)
   subprocess.run(['cc','-std=gnu99','-Wall','-Werror','-I',str(ROOT/'include'),str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True,text=True)
   result=subprocess.run([str(p/'test')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
if __name__=='__main__':unittest.main()
