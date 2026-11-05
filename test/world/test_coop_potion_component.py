"""Compile the actual potion rules, independent of network or user saves."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class CoopPotionTest(unittest.TestCase):
 def test_generation_three_amounts_and_non_effects(self):
  main=r'''
#include "global.h"
#include "constants/items.h"
#include "platform/world_coop_potion.h"
#include <assert.h>
int main(void){
 assert(WorldCoop_IsPotion(ITEM_POTION));assert(!WorldCoop_IsPotion(ITEM_FULL_RESTORE));
 assert(WorldCoop_PotionHeal(ITEM_POTION,1,100)==20);
 assert(WorldCoop_PotionHeal(ITEM_SUPER_POTION,40,100)==50);
 assert(WorldCoop_PotionHeal(ITEM_HYPER_POTION,10,300)==200);
 assert(WorldCoop_PotionHeal(ITEM_MAX_POTION,1,999)==998);
 assert(WorldCoop_PotionHeal(ITEM_POTION,95,100)==5);
 assert(!WorldCoop_PotionHeal(ITEM_POTION,0,100));
 assert(!WorldCoop_PotionHeal(ITEM_POTION,100,100));
 assert(!WorldCoop_PotionHeal(ITEM_POTION,101,100));
 assert(!WorldCoop_PotionHeal(ITEM_POTION,1,1000));
 assert(!WorldCoop_PotionHeal(ITEM_FULL_RESTORE,1,100));
 return 0;
}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'global.h').write_text('#include <stdint.h>\ntypedef uint16_t u16;typedef uint8_t bool8;\n');(p/'main.c').write_text(main)
   q=subprocess.run(['cc','-std=c99','-DPORTABLE','-Wall','-Wextra','-Werror','-I',str(p),'-I',str(ROOT/'include'),str(ROOT/'src/platform/world_coop_potion.c'),str(p/'main.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
