#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stddef.h>
typedef uint64_t u64;typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int bool8;typedef int bool32;
#define TRUE 1
#define FALSE 0
#define NUM_APPRENTICES 16
#define APPRENTICE_LVL_MODE_50 1
#define APPRENTICE_LVL_MODE_OPEN 2
#define TRAINER_ID_LENGTH 4
#define MULTI_PARTY_SIZE 3
#define PARTY_SIZE 6
#define MAX_MON_MOVES 4
#define NUM_SPECIES 1000
#define SPECIES_EGG 999
#define MOVES_COUNT_ALL 900
#define MAP_GROUP(x) ((x)==2?34:3)
#define MAP_GENERATED_WORLD_CAVE 2
#define MAP_NUM(x) 4
#define MAP_BATTLE_FRONTIER_BATTLE_TOWER_LOBBY 1
#define B_TRAINER_PARTNER 1
#define B_TRAINER_PLAYER 0
#define B_SIDE_PLAYER 0
#define REGION_HOENN 0
#define MAP_TYPE_ROUTE 1
#define MAP_TYPE_OCEAN_ROUTE 2
#define MAP_TYPE_UNDERGROUND 3
#define BATTLE_TYPE_DOUBLE 1
#define BATTLE_TYPE_MULTI 2
#define BATTLE_TYPE_INGAME_PARTNER 4
#define B_OUTCOME_LOST 2
#define TRAINER_RECORD_MIXING_APPRENTICE 300
#define MON_DATA_HP 0
#define MON_DATA_HELD_ITEM 1
#define FNPC_FLAG_HEAL_AFTER_FOLLOWER_BATTLE 0
#define FNPC_ALWAYS 1
#define PYRAMID_LOCATION_NONE 0
#define BATTLE_TYPE_PYRAMID 8
#define VAR_TEMP_E 0
#define GAME_STAT_TOTAL_BATTLES 0
#define GAME_STAT_WILD_BATTLES 1
#define BG_PLTT 0
#define BG_PLTT_SIZE 0
#define B_BATTLER_2 2
#define DIFFICULTY_NORMAL 0
#define AI_FLAG_CHECK_BAD_MOVE 1
#define AI_FLAG_CHECK_VIABILITY 2
#define AI_FLAG_TRY_TO_FAINT 4
#define AI_FLAG_DOUBLE_BATTLE 8
#define AI_FLAG_SMART_SWITCHING 16
#define AI_FLAG_SMART_MON_CHOICES 32
#define AI_FLAG_PREDICT_INCOMING_MON 64
#define AI_FLAG_PREDICT_SWITCH 128
#define AI_FLAG_DYNAMIC_FUNC 256
#define BATTLE_TYPE_RECORDED 16
#define BATTLE_TYPE_SAFARI 32
#define BATTLE_TYPE_ROAMER 64
#define BATTLE_TYPE_FIRST_BATTLE 128
#define BATTLE_TYPE_FACTORY 256
#define BATTLE_TYPE_FRONTIER 512
#define BATTLE_TYPE_EREADER_TRAINER 1024
#define BATTLE_TYPE_TRAINER_HILL 2048
#define BATTLE_TYPE_SECRET_BASE 4096
#define AI_FLAG_SAFARI 0
#define AI_FLAG_ROAMING 0
#define AI_FLAG_FIRST_BATTLE 0
#define EW_APPRENTICE_WALKING 0
#define EWRAM_DATA
#define B_MULTI_HALF_TEAMS 0
#define B_TRAINER_OPPONENT_A 2
#define B_TRAINER_OPPONENT_B 3
#define TRAINER_PARTNER(x) (500+(x))
#define PARTNER_NONE 0
#define PARTNER_STEVEN 1
#define B_TRANSITION_SLICE 0
#define B_COMM_TO_CONTROLLER 0
#define REQUEST_HELDITEM_BATTLE 0
#define BATTLE_TYPE_TRAINER 8192
#define BATTLE_TYPE_LINK 16384
#define MON_DATA_SPECIES 2
#define ITEM_NONE 0
enum Item { ITEM_TEST=1 };
enum BattlerId { B0, B1, B2, B3 };
enum DifficultyLevel { DN };
struct Pokemon {u32 hp,pp,item,species;};
struct ApprenticeMon {u16 species,moves[4],item;};
struct Apprentice {u8 id,lvlMode,numQuestions,number;struct ApprenticeMon party[3];u8 playerId[4];u32 checksum;};
static struct {struct Apprentice apprentices[1];u8 playerTrainerId[4];} save2,*gSaveBlock2Ptr=&save2;
static struct {struct {int mapGroup,mapNum;} location;} save1,*gSaveBlock1Ptr=&save1;
static struct {int mapType;} gMapHeader;
static struct {bool8 inBattle;void (*callback2)(void);void(*savedCallback)(void);} gMain;
static struct Pokemon gParties[4][6];static u8 gPartiesCount[4];static u16 gPartnerTrainerId;static u32 gBattleTypeFlags;static u8 gBattleOutcome;
static bool8 connected=1, supported=1,script=0,link=0,coop=0, follower=0,steven=0,pike=0,safari=0,hill=0,sWorldWildFallback=0;
static unsigned region=0,pyramid=0,started=0,returned=0,whiteout=0;
static void CB2_Overworld(void){}static void CB2_WhiteOut(void){whiteout++;}static void CB2_ReturnToField(void){returned++;}
static void FieldCB_ReturnToFieldNoScriptCheckMusic(void){}static void(*gFieldCallback)(void);
static bool8 WorldBridge_ConnectionActive(void){return connected;}static unsigned GetCurrentRegion(void){return region;}static bool8 NativeLink_IsActive(void){return link;}
static bool8 BattleSetup_StevenSupported(void){return supported&&!gMain.inBattle&&!link&&!follower;}
static bool8 ScriptContext_IsEnabled(void){return script;}
static u32 GetMonData(const struct Pokemon*p,unsigned field){return field==MON_DATA_HP?p->hp:p->item;}
static void SetMonData(struct Pokemon*p,unsigned field,const void*v){assert(field==MON_DATA_HELD_ITEM);p->item=*(const enum Item*)v;}
static void CreateApprenticeMon(struct Pokemon*p,const struct Apprentice*a,u8 i){*p=(struct Pokemon){100,10,a->party[i].item,a->party[i].species};}
static unsigned GetBattlerTrainer(unsigned battler){return battler==2?B_TRAINER_PARTNER:battler==0?B_TRAINER_PLAYER:2;}
static void WorldApprenticeWalk_Reset(void){}
void WorldApprentice_Tick(void);
#include "ACTUAL_SOURCE"
static void LockPlayerFieldControls(void){}static void FreezeObjectEvents(void){}static void StopPlayerAvatar(void){}
static bool8 IsNPCFollowerWildBattle(void){return follower;}static unsigned CurrentBattlePyramidLocation(void){return pyramid;}static bool8 WorldActivity_TryCoopWildBattle(void){return coop;}
static bool8 GetSafariZoneFlag(void){return safari;}static bool8 InBattlePike(void){return pike;}static bool8 InTrainerHillChallenge(void){return hill;}
static bool8 TryStevenWildPartner(void){return steven;}static void FinishStevenWildPartner(void){}
static void VarSet(unsigned a,unsigned b){}static void CreateBattleStartTask(unsigned a,unsigned b){started++;}static unsigned GetWildBattleTransition(void){return 0;}
static void IncrementGameStat(unsigned a){}static void IncrementDailyWildBattles(void){}static void TryUpdateGymLeaderRematchFromWild(void){}
static void CpuFill16(unsigned a,void*b,unsigned c){}static void ResetOamRange(unsigned a,unsigned b){}
static void RestorePartyAfterFollowerNPCBattle(void){assert(0);}static bool8 FlagGet(unsigned a){return 0;}static void HealPlayerParty(void){assert(0);}
static bool8 IsPlayerDefeated(unsigned outcome){return outcome==B_OUTCOME_LOST;}static void SetMainCallback2(void(*fn)(void)){gMain.callback2=fn;fn();}static void DowngradeBadPoison(void){}
static bool32 IsSmartBattle(void){return 0;}
static u64 GetWildAiFlags(void){return 0;}static u64 GetAiScriptsInRecordedBattle(unsigned b){return 0;}static u64 GetAiScriptsInBattleFactory(void){return 0;}static u64 GetTrainerAIFlagsFromId(unsigned t){assert(0);return 0;}
static bool32 IsDoubleBattle(void){return 1;}static void *sDynamicAiFunc;
static enum DifficultyLevel GetCurrentDifficultyLevel(void){return 1;}
static struct {void *party;} gBattlePartners[2][4];
ACTUAL_IDENTITY
static void CB2_EndWildBattle(void);
ACTUAL_ENTRY_EXIT
static void checksum(void){u32 n=0,w;for(unsigned i=0;i<offsetof(struct Apprentice,checksum);i+=4){memcpy(&w,(u8*)&save2.apprentices[0]+i,4);n+=w;}save2.apprentices[0].checksum=n;}
static void setup(void){memset(&sOuting,0,sizeof(sOuting));memset(&save2,0,sizeof(save2));save2.apprentices[0].id=2;save2.apprentices[0].lvlMode=1;save2.apprentices[0].number=1;for(unsigned i=0;i<3;i++){save2.apprentices[0].party[i].species=i+10;save2.apprentices[0].party[i].moves[0]=20;save2.apprentices[0].party[i].item=55;}checksum();save1.location.mapGroup=3;save1.location.mapNum=4;gMain.callback2=CB2_Overworld;gMain.inBattle=0;connected=supported=1;region=0;link=coop=follower=steven=pike=safari=hill=sWorldWildFallback=0;pyramid=0;gMapHeader.mapType=1;gPartnerTrainerId=77;gPartiesCount[1]=5;memset(gParties,0,sizeof(gParties));gParties[0][0]=(struct Pokemon){80,9,99,20};gParties[1][0]=(struct Pokemon){42,6,13,30};gBattleOutcome=1;}
int main(void){char out[160];setup();assert(WorldApprentice_Command("/apprentice start",out,sizeof(out)));
#if !EW_APPRENTICE_OUTINGS
assert(!sOuting.ready);assert(!WorldApprentice_TryWild());assert(!WorldApprentice_BlockItemTransfer(0,2));return 0;
#else
assert(sOuting.ready);assert(sOuting.party[0].item==0);struct Pokemon savedPlayer[6],savedPartner[6];memcpy(savedPlayer,gParties[0],sizeof(savedPlayer));memcpy(savedPartner,gParties[1],sizeof(savedPartner));struct Apprentice record=save2.apprentices[0];
coop=1;DoStandardWildBattle(0);assert(!sOuting.active);coop=0;DoStandardWildBattle(0);assert(sOuting.active&&gPartnerTrainerId==300&&gPartiesCount[1]==3);assert(GetBattlePartnerDifficultyLevel(gPartnerTrainerId)==DIFFICULTY_NORMAL);assert(GetAiFlags(gPartnerTrainerId,B_BATTLER_2)==15);assert(!memcmp(savedPlayer,gParties[0],sizeof(savedPlayer)));assert(WorldApprentice_BlockItemTransfer(0,2));assert(WorldApprentice_BlockItemTransfer(2,1));assert(!WorldApprentice_BlockItemTransfer(0,1));assert(!WorldApprentice_BlockItemTransfer(2,2));
gParties[1][0].hp=17;gParties[1][0].pp=3;gParties[0][0].hp=65;CB2_EndWildBattle();assert(!sOuting.active&&sOuting.ready&&sOuting.battles==1);assert(sOuting.party[0].hp==17&&sOuting.party[0].pp==3);assert(gParties[0][0].hp==65);assert(!memcmp(savedPartner,gParties[1],sizeof(savedPartner))&&gPartnerTrainerId==77&&gPartiesCount[1]==5);assert(!memcmp(&record,&save2.apprentices[0],sizeof(record)));
DoStandardWildBattle(0);assert(gParties[1][0].hp==17);WorldApprentice_Reset(0);assert(sOuting.active&&!sOuting.ready);CB2_EndWildBattle();assert(!sOuting.active&&!sOuting.ready);assert(!memcmp(savedPartner,gParties[1],sizeof(savedPartner)));
setup();WorldApprentice_Command("/apprentice start",out,sizeof(out));save2.apprentices[0].number++;checksum();assert(!WorldApprentice_TryWild()&&!sOuting.ready);
setup();WorldApprentice_Command("/apprentice start",out,sizeof(out));sWorldWildFallback=1;DoStandardWildBattle(0);assert(!sOuting.active);sWorldWildFallback=0;steven=1;DoStandardWildBattle(0);assert(!sOuting.active);steven=0;safari=1;DoStandardWildBattle(0);assert(!sOuting.active);safari=0;DoStandardWildBattle(1);assert(!sOuting.active);
setup();WorldApprentice_Command("/apprentice start",out,sizeof(out));save1.location.mapGroup=34;assert(!WorldApprentice_TryWild());
setup();WorldApprentice_Command("/apprentice start",out,sizeof(out));region=1;WorldApprentice_Tick();assert(!sOuting.ready);
setup();save2.apprentices[0].checksum++;WorldApprentice_Command("/apprentice start",out,sizeof(out));assert(!sOuting.ready);
setup();WorldApprentice_Command("/apprentice start",out,sizeof(out));DoStandardWildBattle(0);gBattleOutcome=B_OUTCOME_LOST;CB2_EndWildBattle();assert(whiteout&&!sOuting.ready);
setup();WorldApprentice_Command("/apprentice start",out,sizeof(out));DoStandardWildBattle(0);for(unsigned i=0;i<3;i++)gParties[1][i].hp=0;CB2_EndWildBattle();assert(!sOuting.ready);
setup();WorldApprentice_Command("/apprentice start",out,sizeof(out));WorldApprentice_Command("/apprentice end",out,sizeof(out));assert(!WorldApprentice_TryWild());assert(!memcmp(&record,&save2.apprentices[0],sizeof(record)));
puts("apprentice entry/battle/exit synthetic checks passed");return 0;
#endif
}
