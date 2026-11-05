"""Exercise the actual battle-only adapter against disposable battle stubs."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class GameAdapterTests(unittest.TestCase):
 def test_owner_isolation_and_no_party_mutation(self):
  main=r'''
#include "global.h"
#include "battle.h"
#include "pokemon.h"
#include "constants/species.h"
#include "constants/items.h"
#include "constants/pokemon.h"
#include "constants/abilities.h"
#include "platform/mega_game.h"
#include "platform/mega_forms.h"
#include <assert.h>
#include <string.h>
struct Pokemon gPlayerParty[6],gEnemyParty[6];struct BattlePokemon gBattleMons[4];
u8 gBattlersCount=4,gBattlerPartyIndexes[4];u32 gBattleTypeFlags;int hasKey=1;
int FlagGet(int x){(void)x;return 1;}int NativeLink_IsActive(void){return 1;}
int CheckBagHasItem(u16 x,u16 y){(void)x;(void)y;return hasKey;}
u8 GetBattlerPosition(u8 x){return x;}u8 GetBattlerSide(u8 x){return x&1;}
u8 GetNature(struct Pokemon *p){(void)p;return 0;}
u16 ModifyStatByNature(u8 n,u16 s,u8 i){(void)n;(void)i;return s;}
u32 GetMonData(struct Pokemon *p,int field){
 if(field==MON_DATA_SPECIES)return p->species;
 if(field>=MON_DATA_ATK_IV && field<=MON_DATA_SPDEF_IV)return 31;
 if(field>=MON_DATA_ATK_EV && field<=MON_DATA_SPDEF_EV)return 252;
 return 0;
}
int main(void){
 struct Pokemon before[6];
 gPlayerParty[0].species=SPECIES_VENUSAUR;gPlayerParty[3].species=SPECIES_GENGAR;
 memcpy(before,gPlayerParty,sizeof(before));
 gBattlerPartyIndexes[0]=0;gBattlerPartyIndexes[2]=3;
 gBattleMons[0].species=SPECIES_VENUSAUR;gBattleMons[0].item=ITEM_VENUSAURITE;gBattleMons[0].hp=30;gBattleMons[0].level=50;
 gBattleMons[2].species=SPECIES_GENGAR;gBattleMons[2].item=ITEM_GENGARITE;gBattleMons[2].hp=30;gBattleMons[2].level=50;
 MegaGame_Reset();hasKey=0;assert(!MegaGame_CanSelect(0));hasKey=1;
 assert(MegaGame_CanSelect(0));assert(MegaGame_ToggleSelection(0));
 assert(MegaGame_ChoiceBit(0)==MEGA_MOVE_CHOICE_BIT);
 assert(!MegaGame_ToggleSelection(2));
 MegaGame_ClearSelection(0);assert(!MegaGame_ChoiceBit(0));
 assert(MegaGame_Queue(0));
 assert(!MegaGame_CanQueue(2)); /* ordinary doubles share one trainer */
 assert(MegaGame_Apply(0));assert(gBattleMons[0].attack==152 && gBattleMons[0].ability==ABILITY_THICK_FAT);
 assert(!memcmp(before,gPlayerParty,sizeof(before)));assert(!MegaGame_CanQueue(0));
 /* Another slot does not inherit the form; switching the original back in
  * restores it without spending a second use or writing party data. */
 gPlayerParty[1].species=SPECIES_GENGAR;before[1]=gPlayerParty[1];
 gBattlerPartyIndexes[0]=1;gBattleMons[0].species=SPECIES_GENGAR;gBattleMons[0].attack=1;
 MegaGame_OnSwitchIn(0);assert(!MegaGame_ActiveForm(0));assert(gBattleMons[0].attack==1);
 gBattlerPartyIndexes[0]=0;gBattleMons[0].species=SPECIES_VENUSAUR;gBattleMons[0].attack=1;
 MegaGame_OnSwitchIn(0);assert(MegaGame_ActiveForm(0)==MEGA_FORM_VENUSAUR_MEGA);
 assert(gBattleMons[0].attack==152 && !MegaGame_CanQueue(0));
 assert(!memcmp(before,gPlayerParty,sizeof(before)));
 MegaGame_Reset();gBattleTypeFlags=BATTLE_TYPE_MULTI;
 assert(MegaGame_Queue(0));assert(MegaGame_Queue(2));
 assert(MegaGame_Apply(0));assert(MegaGame_Apply(2));
 assert(!memcmp(before,gPlayerParty,sizeof(before)));
 assert(MegaGame_ActiveForm(0)==MEGA_FORM_VENUSAUR_MEGA);
 assert(MegaGame_ActiveForm(2)==MEGA_FORM_GENGAR_MEGA);
 MegaGame_Reset();gBattleMons[0].status2=STATUS2_TRANSFORMED;assert(!MegaGame_CanQueue(0));
 return 0;
}'''
  globalh='''#include <stdint.h>\n#include <stddef.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef uint8_t bool8;\n#define TRUE 1\n#define FALSE 0\n#define PARTY_SIZE 6\n#define MULTI_PARTY_SIZE 3\n#define MAX_BATTLERS_COUNT 4\n'''
  battleh='''#include "global.h"\n#define BATTLE_TYPE_MULTI 1\n#define BATTLE_TYPE_LINK 2\n#define BATTLE_TYPE_RECORDED 4\n#define BATTLE_TYPE_RECORDED_LINK 8\n#define B_SIDE_PLAYER 0\n#define STATUS2_TRANSFORMED 1\nstruct BattlePokemon {u16 species,item,hp,level,attack,defense,speed,spAttack,spDefense;u8 types[2],ability;u32 status2;};\nextern struct BattlePokemon gBattleMons[4];extern u8 gBattlersCount,gBattlerPartyIndexes[4];extern u32 gBattleTypeFlags;u8 GetBattlerPosition(u8);u8 GetBattlerSide(u8);\n'''
  pokemonh='''#include "global.h"\nstruct Pokemon {u16 species;};extern struct Pokemon gPlayerParty[6],gEnemyParty[6];\nenum {MON_DATA_SPECIES,MON_DATA_ATK_IV,MON_DATA_DEF_IV,MON_DATA_SPEED_IV,MON_DATA_SPATK_IV,MON_DATA_SPDEF_IV,MON_DATA_ATK_EV,MON_DATA_DEF_EV,MON_DATA_SPEED_EV,MON_DATA_SPATK_EV,MON_DATA_SPDEF_EV};\nu32 GetMonData(struct Pokemon *,int);u8 GetNature(struct Pokemon *);u16 ModifyStatByNature(u8,u16,u8);\n'''
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'constants').mkdir();(root/'platform').mkdir()
   (root/'global.h').write_text('#ifndef GLOB\n#define GLOB\n'+globalh+'#endif\n')
   (root/'battle.h').write_text(battleh);(root/'battle_anim.h').write_text('');(root/'pokemon.h').write_text(pokemonh)
   (root/'item.h').write_text('int CheckBagHasItem(u16,u16);\n');(root/'event_data.h').write_text('int FlagGet(int);\n')
   (root/'constants/flags.h').write_text('#define FLAG_MEGA_EVOLUTION 1\n')
   for n in ('species.h','pokemon.h','abilities.h','items.h'):shutil.copy(ROOT/'include/constants'/n,root/'constants'/n)
   for n in ('mega_game.h','mega_battle.h','mega_forms.h'):shutil.copy(ROOT/'include/platform'/n,root/'platform'/n)
   (root/'platform/native_link.h').write_text('int NativeLink_IsActive(void);\n');(root/'main.c').write_text(main)
   cmd=['cc','-std=c99','-DPORTABLE','-DMEGA_FEATURE_READY=1','-Wall','-Wextra','-Werror','-I',str(root)]+[str(ROOT/'src/platform'/x) for x in ('mega_forms.c','mega_battle.c','mega_game.c')]+[str(root/'main.c'),'-o',str(root/'test')]
   result=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
   result=subprocess.run([str(root/'test')],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
if __name__=='__main__':unittest.main()
