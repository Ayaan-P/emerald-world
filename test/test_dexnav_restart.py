"""Real C battle-credit/sidecar/restart integration with production NativeSave I/O.
Enemy/trainer are controlled ABI stubs. This is not native gameplay evidence.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from test_dexnav_lifecycle import function
from test_dexnav_progress import c_function

ROOT=Path(__file__).resolve().parents[1]
class DexNavRestart(unittest.TestCase):
    def test_won_caught_fail_once_only_and_private_process_restart(self):
        source=(ROOT/'src/platform/dexnav_native.c').read_text()
        dex=(ROOT/'src/dexnav.c').read_text()
        header=(ROOT/'include/dexnav.h').read_text()
        encounter=re.search(r'enum EncounterType\s*\{.*?\};',header,re.S).group()
        mask=re.search(r'^#define DEXNAV_MASK_SPECIES\s+\S+',header,re.M).group()
        names=['ProgressChecksum','ValidProgress','ProgressSequence','NewestProgressSlot','ExpandedProgressSize','ExpandedProgressChecksum','ValidExpandedProgress','LoadExpandedProgress','PersistExpandedProgress','BindTrainer','DexNavNative_Init','DexNavNative_Persist','DexNavNative_SetBattleOwner','DexNavNative_OwnsWildMon','DexNavNative_BattleFinished']
        state=source[source.index('static u8 sTrainer[4]'):source.index('static u16 sBgPalette')]
        c=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include "constants/species.h"
#include "constants/battle.h"
#include "config/dexnav.h"
#include "platform/native_save.h"
typedef uint8_t u8;typedef uint16_t u16;typedef int16_t s16;typedef uint32_t u32;typedef u8 bool8;
#define TRUE 1
#define FALSE 0
#define MON_DATA_SPECIES 0
#define MON_DATA_PERSONALITY 1
struct Mon{u16 species;u32 personality;}gEnemyParty[1];
static struct {u8 playerTrainerId[4];}trainer,*gSaveBlock2Ptr=&trainer;
static struct {u16 registeredSpecies,detectorSteps;u8 dexNavChain,dexNavSearchLevels[SPECIES_TABLE_COUNT];bool8 searching;}gDexNavNativeState;
static u16 sBattleOwner,gDexNavSpecies;static u32 sBattlePersonality;
static u32 GetMonData(struct Mon *m,unsigned f){return f==MON_DATA_SPECIES?m->species:m->personality;}
''' + encounter+'\n'+mask+'\n'+state+'\n'+function(dex,'IncrementDexNavChain')+'\n'+'\n'.join((c_function(source,n) if n=='ProgressSequence' else function(source,n))for n in names)+r'''
int main(int argc,char **argv){
 assert(argc==3);
 memcpy(trainer.playerTrainerId,"ABCD",4);
 if(!strcmp(argv[2],"other"))trainer.playerTrainerId[0]='Z';
 DexNavNative_Init(argv[1],TRUE);BindTrainer();
 if(!strcmp(argv[2],"write")){
  gDexNavNativeState.registeredSpecies=SPECIES_POOCHYENA;
  gEnemyParty[0]=(struct Mon){SPECIES_POOCHYENA,12345};
  DexNavNative_SetBattleOwner(SPECIES_POOCHYENA);
  DexNavNative_BattleFinished(B_OUTCOME_WON);
  DexNavNative_BattleFinished(B_OUTCOME_WON);
  assert(gDexNavNativeState.dexNavSearchLevels[SPECIES_POOCHYENA]==1);
  assert(gDexNavNativeState.dexNavChain==1);
  DexNavNative_SetBattleOwner(SPECIES_POOCHYENA);
  DexNavNative_BattleFinished(B_OUTCOME_CAUGHT);
  assert(gDexNavNativeState.dexNavSearchLevels[SPECIES_POOCHYENA]==2);
  assert(gDexNavNativeState.dexNavChain==2);
  DexNavNative_SetBattleOwner(SPECIES_POOCHYENA);
  DexNavNative_BattleFinished(B_OUTCOME_RAN);
  assert(gDexNavNativeState.dexNavChain==0);
  assert(gDexNavNativeState.dexNavSearchLevels[SPECIES_POOCHYENA]==2);
  gDexNavNativeState.dexNavChain=DEXNAV_CHAIN_MAX;
  gDexNavNativeState.dexNavSearchLevels[SPECIES_POOCHYENA]=255;
  DexNavNative_SetBattleOwner(SPECIES_POOCHYENA);
  DexNavNative_BattleFinished(B_OUTCOME_WON);
  assert(gDexNavNativeState.dexNavChain==DEXNAV_CHAIN_MAX);
  assert(gDexNavNativeState.dexNavSearchLevels[SPECIES_POOCHYENA]==255);
 }else if(!strcmp(argv[2],"read")){
  assert(gDexNavNativeState.registeredSpecies==SPECIES_POOCHYENA);
  assert(gDexNavNativeState.dexNavSearchLevels[SPECIES_POOCHYENA]==255);
  assert(gDexNavNativeState.dexNavChain==0 && sBattleOwner==SPECIES_NONE);
 }else{
  assert(!strcmp(argv[2],"other"));
  assert(gDexNavNativeState.registeredSpecies==0);
  assert(gDexNavNativeState.dexNavSearchLevels[SPECIES_POOCHYENA]==0);
 }
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='dexnav-restart-')as tmp:
            p=Path(tmp);(p/'test.c').write_text(c)
            compiled=subprocess.run(['cc','-std=gnu99','-Wall','-Werror','-DPORTABLE','-iquote',str(ROOT/'include'),str(p/'test.c'),str(ROOT/'src/platform/native_save.c'),'-o',str(p/'test')],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            save=p/'original.sav';save.write_bytes(b'unchanged original trainer save')
            for mode in ('write','read','other','read'):
                run=subprocess.run([str(p/'test'),str(save),mode],capture_output=True,text=True)
                self.assertEqual(run.returncode,0,run.stderr)
            sidecar=Path(str(save)+'.dexnav')
            self.assertEqual(sidecar.stat().st_mode&0o777,0o600)
            self.assertEqual(save.read_bytes(),b'unchanged original trainer save')
            self.assertTrue(sidecar.read_bytes().startswith(b'DNV2'))

if __name__=='__main__':unittest.main()
