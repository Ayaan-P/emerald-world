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
static int bag[256],hp=35,maxhp=100,statusSends;static u32 generation=42,statusValue;static u8 packet[20];
u32 GetMonData2(struct Pokemon *mon,s32 field){(void)mon;if(field==MON_DATA_HP)return hp;if(field==MON_DATA_MAX_HP)return maxhp;if(field==MON_DATA_STATUS)return statusValue;return 0;}
bool8 CheckBagHasItem(u16 id,u16 n){return id<256 && bag[id]>=n;}
bool8 RemoveBagItem(u16 id,u16 n){if(!CheckBagHasItem(id,n))return FALSE;bag[id]-=n;return TRUE;}
bool8 AddBagItem(u16 id,u16 n){if(id>=256)return FALSE;bag[id]+=n;return TRUE;}
uint32_t NativeLink_Generation(void){return generation;}
void NativeLink_Abort(void){generation=0;}
void PrepareBufferDataTransferLink(u8 id,u16 size,u8 *p){assert(id==B_COMM_TO_CONTROLLER && size==16);memset(packet,0,sizeof(packet));memcpy(packet,p,size);}
void MarkBattlerForControllerExec(u8 b){(void)b;gBattleControllerExecFlags=1;}
void BtlController_EmitSetMonData(u8 id,u8 request,u8 mask,u8 bytes,void *data){
 assert(id==B_COMM_TO_CONTROLLER && request==REQUEST_STATUS_BATTLE && !mask && bytes==4);
 assert(*(u32 *)data==0);statusSends++;
}
int main(void){
 struct CoopHeader header={0};header.magic=COOP_MAGIC;header.version=COOP_VERSION;header.count=1;
 assert(HeaderValid(&header,0));header.version=3;assert(!HeaderValid(&header,0));header.version=4;assert(!HeaderValid(&header,0));
 sCoop.state=COOP_BATTLE;sCoop.generation=42;sCoop.local=1;gBattlerPartyIndexes[2]=3;
 gBattleMons[2].hp=35;gBattleMons[2].maxHP=100;gActiveBattler=gBattlerInMenuId=2;
 bag[ITEM_SUPER_POTION]=2;assert(WorldCoop_CanUseMedicine(ITEM_SUPER_POTION));
 assert(WorldCoop_ItemReplyValid(0));
 assert(WorldCoop_ItemReplyValid(WORLD_COOP_MEDICINE_REPLY|ITEM_SUPER_POTION));
 assert(!WorldCoop_ItemReplyValid(WORLD_COOP_MEDICINE_REPLY|ITEM_REVIVE));
 sCoop.kind=1;assert(WorldCoop_ItemReplyValid(0));
 assert(WorldCoop_ItemReplyValid(WORLD_COOP_MEDICINE_REPLY|ITEM_SUPER_POTION));
 assert(!WorldCoop_ItemReplyValid(ITEM_POKE_BALL));sCoop.kind=0;
 sCoop.pendingMedicine=ITEM_SUPER_POTION;
 assert(WorldCoop_BeginMedicineAction(2,WORLD_COOP_MEDICINE_REPLY|ITEM_SUPER_POTION)==0);
 assert(WorldCoop_MedicinePacketValid(packet,20));
 packet[16]=1;assert(!WorldCoop_MedicinePacketValid(packet,20));packet[16]=0;
 packet[4]^=1;assert(!WorldCoop_MedicinePacketValid(packet,20));packet[4]^=1;
 packet[2]=1;assert(!WorldCoop_ConsumeMedicine(packet));packet[2]=2;
 hp=36;assert(!WorldCoop_ConsumeMedicine(packet));assert(bag[ITEM_SUPER_POTION]==2);hp=35;
 assert(WorldCoop_ConsumeMedicine(packet));
 assert(bag[ITEM_SUPER_POTION]==1 && hp==35);assert(!WorldCoop_ConsumeMedicine(packet));
 assert(WorldCoop_AdvanceMedicineAction(2)==0);gBattleControllerExecFlags=0;
 gBattleBufferB[2][0]=CONTROLLER_TWORETURNVALUES;gBattleBufferB[2][1]=1;
 assert(WorldCoop_AdvanceMedicineAction(2)==1 && gBattleMoveDamage==-50 && gLastUsedItem==ITEM_SUPER_POTION);
 WorldCoop_Abort();assert(bag[ITEM_SUPER_POTION]==2);
 /* First player also consumes only their own bag and rolls back on abort. */
 generation=43;memset(&sCoop,0,sizeof(sCoop));sCoop.state=COOP_BATTLE;sCoop.generation=43;sCoop.local=0;
 gActiveBattler=gBattlerInMenuId=0;gBattlerPartyIndexes[0]=0;gBattleMons[0].hp=35;gBattleMons[0].maxHP=100;
 bag[ITEM_POTION]=1;sCoop.pendingMedicine=ITEM_POTION;
 assert(WorldCoop_BeginMedicineAction(0,WORLD_COOP_MEDICINE_REPLY|ITEM_POTION)==0);
 assert(WorldCoop_ConsumeMedicine(packet));assert(!bag[ITEM_POTION]);
 WorldCoop_Abort();assert(bag[ITEM_POTION]==1);
 /* An antidote cures status through the standard controllers. */
 generation=44;memset(&sCoop,0,sizeof(sCoop));sCoop.state=COOP_BATTLE;sCoop.generation=44;sCoop.local=0;
 gActiveBattler=gBattlerInMenuId=0;gBattlerPartyIndexes[0]=0;hp=35;maxhp=100;statusValue=STATUS1_TOXIC_POISON;
 gBattleMons[0].hp=35;gBattleMons[0].maxHP=100;gBattleMons[0].status1=statusValue | STATUS1_TOXIC_TURN(3);
 bag[ITEM_ANTIDOTE]=1;sCoop.pendingMedicine=ITEM_ANTIDOTE;
 assert(WorldCoop_BeginMedicineAction(0,WORLD_COOP_MEDICINE_REPLY|ITEM_ANTIDOTE)==0);
 statusValue=0;assert(!WorldCoop_ConsumeMedicine(packet));assert(bag[ITEM_ANTIDOTE]==1);
 statusValue=STATUS1_TOXIC_POISON;assert(WorldCoop_ConsumeMedicine(packet));assert(!bag[ITEM_ANTIDOTE]);
 gBattleControllerExecFlags=0;gBattleBufferB[0][0]=CONTROLLER_TWORETURNVALUES;gBattleBufferB[0][1]=1;
 assert(WorldCoop_AdvanceMedicineAction(0)==2 && gBattleMoveDamage==0);
 assert(!gBattleMons[0].status1 && statusSends==1 && gBattleControllerExecFlags);
 WorldCoop_Abort();assert(bag[ITEM_ANTIDOTE]==1);
 /* Awakening also clears Nightmare, matching the native medicine effect. */
 generation=45;memset(&sCoop,0,sizeof(sCoop));sCoop.state=COOP_BATTLE;sCoop.generation=45;sCoop.local=0;
 gActiveBattler=gBattlerInMenuId=0;gBattlerPartyIndexes[0]=0;statusValue=STATUS1_SLEEP;
 gBattleMons[0].hp=35;gBattleMons[0].maxHP=100;gBattleMons[0].status1=statusValue;
 gBattleMons[0].status2=STATUS2_NIGHTMARE;bag[ITEM_AWAKENING]=1;sCoop.pendingMedicine=ITEM_AWAKENING;
 assert(WorldCoop_BeginMedicineAction(0,WORLD_COOP_MEDICINE_REPLY|ITEM_AWAKENING)==0);
 assert(WorldCoop_ConsumeMedicine(packet));gBattleControllerExecFlags=0;
 gBattleBufferB[0][0]=CONTROLLER_TWORETURNVALUES;gBattleBufferB[0][1]=1;
 assert(WorldCoop_AdvanceMedicineAction(0)==2 && !gBattleMons[0].status1);
 assert(!(gBattleMons[0].status2 & STATUS2_NIGHTMARE) && statusSends==2);
 WorldCoop_Abort();assert(bag[ITEM_AWAKENING]==1);
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
