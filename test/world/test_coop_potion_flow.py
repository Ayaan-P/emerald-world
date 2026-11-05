"""Compile actual co-op ownership, packet and rollback code with isolated stubs."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
HARNESS=r'''
#include "src/platform/world_coop.c"
#include <assert.h>
struct Pokemon gPlayerParty[PARTY_SIZE];
u8 gPlayerPartyCount,gActiveBattler,gBattlersCount=4,gBattlerInMenuId;
u16 gBattlerPartyIndexes[MAX_BATTLERS_COUNT],gLastUsedItem;
u32 gBattleTypeFlags,gBattleControllerExecFlags;
u8 gBattleBufferB[MAX_BATTLERS_COUNT][0x200];
struct BattlePokemon gBattleMons[MAX_BATTLERS_COUNT];
s32 gBattleMoveDamage;
static int bag[256],hp=35,maxhp=100;static u32 generation=42;static u8 packet[16];
u32 GetMonData2(struct Pokemon *mon,s32 field){(void)mon;if(field==MON_DATA_HP)return hp;if(field==MON_DATA_MAX_HP)return maxhp;return 0;}
bool8 CheckBagHasItem(u16 id,u16 n){return id<256 && bag[id]>=n;}
bool8 RemoveBagItem(u16 id,u16 n){if(!CheckBagHasItem(id,n))return FALSE;bag[id]-=n;return TRUE;}
bool8 AddBagItem(u16 id,u16 n){if(id>=256)return FALSE;bag[id]+=n;return TRUE;}
uint32_t NativeLink_Generation(void){return generation;}
void NativeLink_Abort(void){generation=0;}
void PrepareBufferDataTransferLink(u8 id,u16 size,u8 *p){assert(id==B_COMM_TO_CONTROLLER && size==12);memset(packet,0,sizeof(packet));memcpy(packet,p,size);}
void MarkBattlerForControllerExec(u8 b){(void)b;gBattleControllerExecFlags=1;}
int main(void){
 struct CoopHeader header={0};header.magic=COOP_MAGIC;header.version=COOP_VERSION;header.count=1;
 assert(HeaderValid(&header,0));header.version=3;assert(!HeaderValid(&header,0));
 sCoop.state=COOP_BATTLE;sCoop.generation=42;sCoop.local=1;gBattlerPartyIndexes[2]=3;
 gBattleMons[2].hp=35;gBattleMons[2].maxHP=100;gActiveBattler=gBattlerInMenuId=2;
 bag[ITEM_SUPER_POTION]=2;assert(WorldCoop_CanUsePotion(ITEM_SUPER_POTION));
 assert(WorldCoop_ItemReplyValid(0));
 assert(WorldCoop_ItemReplyValid(WORLD_COOP_POTION_REPLY|ITEM_SUPER_POTION));
 assert(!WorldCoop_ItemReplyValid(WORLD_COOP_POTION_REPLY|ITEM_FULL_RESTORE));
 sCoop.kind=1;assert(WorldCoop_ItemReplyValid(0));
 assert(WorldCoop_ItemReplyValid(WORLD_COOP_POTION_REPLY|ITEM_SUPER_POTION));
 assert(!WorldCoop_ItemReplyValid(ITEM_POKE_BALL));sCoop.kind=0;
 sCoop.pendingPotion=ITEM_SUPER_POTION;
 assert(WorldCoop_BeginPotionAction(2,WORLD_COOP_POTION_REPLY|ITEM_SUPER_POTION)==0);
 assert(WorldCoop_PotionPacketValid(packet,16));
 packet[12]=1;assert(!WorldCoop_PotionPacketValid(packet,16));packet[12]=0;
 packet[4]^=1;assert(!WorldCoop_PotionPacketValid(packet,16));packet[4]^=1;
 packet[2]=1;assert(!WorldCoop_ConsumePotion(packet));packet[2]=2;
 hp=36;assert(!WorldCoop_ConsumePotion(packet));assert(bag[ITEM_SUPER_POTION]==2);hp=35;
 assert(WorldCoop_ConsumePotion(packet));
 assert(bag[ITEM_SUPER_POTION]==1 && hp==35);assert(!WorldCoop_ConsumePotion(packet));
 assert(WorldCoop_AdvancePotionAction(2)==0);gBattleControllerExecFlags=0;
 gBattleBufferB[2][0]=CONTROLLER_TWORETURNVALUES;gBattleBufferB[2][1]=1;
 assert(WorldCoop_AdvancePotionAction(2)==1 && gBattleMoveDamage==-50 && gLastUsedItem==ITEM_SUPER_POTION);
 WorldCoop_Abort();assert(bag[ITEM_SUPER_POTION]==2);
 /* First player also consumes only their own bag and rolls back on abort. */
 generation=43;memset(&sCoop,0,sizeof(sCoop));sCoop.state=COOP_BATTLE;sCoop.generation=43;sCoop.local=0;
 gActiveBattler=gBattlerInMenuId=0;gBattlerPartyIndexes[0]=0;gBattleMons[0].hp=35;gBattleMons[0].maxHP=100;
 bag[ITEM_POTION]=1;sCoop.pendingPotion=ITEM_POTION;
 assert(WorldCoop_BeginPotionAction(0,WORLD_COOP_POTION_REPLY|ITEM_POTION)==0);
 assert(WorldCoop_ConsumePotion(packet));assert(!bag[ITEM_POTION]);
 WorldCoop_Abort();assert(bag[ITEM_POTION]==1);
 return 0;
}
'''
class CoopPotionFlow(unittest.TestCase):
 def test_owner_execution_and_abort_refund(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(HARNESS)
   cmd=['cc','-std=gnu99','-DPORTABLE','-D_(x)=x','-ffunction-sections','-fdata-sections','-Wno-error','-iquote',str(ROOT/'include'),'-iquote',str(ROOT),str(p/'test.c'),str(ROOT/'src/platform/world_coop_potion.c'),'-Wl,--gc-sections','-o',str(p/'test')]
   q=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
