"""Compile the actual potion rules, independent of network or user saves."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class CoopPotionTest(unittest.TestCase):
 def test_generation_three_amounts_and_non_effects(self):
  main=r'''
#include "global.h"
#include "constants/items.h"
#include "constants/battle.h"
#include "platform/world_coop_potion.h"
#include <assert.h>
int main(void){
 assert(WorldCoop_IsHpMedicine(ITEM_POTION));assert(!WorldCoop_IsHpMedicine(ITEM_FULL_RESTORE));
 assert(WorldCoop_HpMedicineHeal(ITEM_POTION,1,100)==20);
 assert(WorldCoop_HpMedicineHeal(ITEM_SUPER_POTION,40,100)==50);
 assert(WorldCoop_HpMedicineHeal(ITEM_HYPER_POTION,10,300)==200);
 assert(WorldCoop_HpMedicineHeal(ITEM_MAX_POTION,1,999)==998);
 assert(WorldCoop_HpMedicineHeal(ITEM_FRESH_WATER,1,500)==50);
 assert(WorldCoop_HpMedicineHeal(ITEM_SODA_POP,1,500)==60);
 assert(WorldCoop_HpMedicineHeal(ITEM_LEMONADE,1,500)==80);
 assert(WorldCoop_HpMedicineHeal(ITEM_MOOMOO_MILK,1,500)==100);
 assert(WorldCoop_HpMedicineHeal(ITEM_POTION,95,100)==5);
 assert(!WorldCoop_HpMedicineHeal(ITEM_POTION,0,100));
 assert(!WorldCoop_HpMedicineHeal(ITEM_POTION,100,100));
 assert(!WorldCoop_HpMedicineHeal(ITEM_POTION,101,100));
 assert(!WorldCoop_HpMedicineHeal(ITEM_POTION,1,1000));
 assert(!WorldCoop_HpMedicineHeal(ITEM_FULL_RESTORE,1,100));
 u16 heal=99;u32 status=99;bool8 clear=0;
 assert(WorldCoop_IsMedicine(ITEM_ANTIDOTE));assert(WorldCoop_IsMedicine(ITEM_FULL_RESTORE));
 assert(WorldCoop_MedicineEffect(ITEM_ANTIDOTE,40,100,STATUS1_TOXIC_POISON | STATUS1_TOXIC_COUNTER,0,&heal,&status,&clear));
 assert(heal==0 && status==0);
 assert(!WorldCoop_MedicineEffect(ITEM_ANTIDOTE,40,100,STATUS1_BURN,0,&heal,&status,&clear));
 assert(WorldCoop_MedicineEffect(ITEM_ICE_HEAL,1,100,STATUS1_FREEZE,0,&heal,&status,&clear) && !status);
 assert(WorldCoop_MedicineEffect(ITEM_PARALYZE_HEAL,1,100,STATUS1_PARALYSIS,0,&heal,&status,&clear) && !status);
 assert(WorldCoop_MedicineEffect(ITEM_BURN_HEAL,40,100,STATUS1_BURN,0,&heal,&status,&clear));
 assert(heal==0 && status==0);
 assert(WorldCoop_MedicineEffect(ITEM_AWAKENING,100,100,STATUS1_SLEEP,0,&heal,&status,&clear));
 assert(heal==0 && status==0);
 assert(!WorldCoop_MedicineEffect(ITEM_BURN_HEAL,0,100,STATUS1_BURN,0,&heal,&status,&clear));
 assert(WorldCoop_MedicineEffect(ITEM_FULL_HEAL,100,100,0,1,&heal,&status,&clear));
 assert(!heal && !status && clear);
 assert(WorldCoop_MedicineEffect(ITEM_FULL_RESTORE,40,100,STATUS1_BURN,1,&heal,&status,&clear));
 assert(heal==60 && !status && clear);
 return 0;
}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint16_t u16;typedef uint32_t u32;typedef uint8_t bool8;\n#define FALSE 0\n#define TRUE 1\n');(p/'main.c').write_text(main)
   q=subprocess.run(['cc','-std=c99','-DPORTABLE','-Wall','-Wextra','-Werror','-I',str(p),'-I',str(ROOT/'include'),str(ROOT/'src/platform/world_coop_potion.c'),str(p/'main.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
