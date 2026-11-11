#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
typedef unsigned char u8,bool8;typedef unsigned short u16;typedef int s32;
#define TRUE 1
#define FALSE 0
#define PARTY_SIZE 6
#define MOVES_COUNT 30
#define DAMAGE_CATEGORY_STATUS 2
#define LEVEL_UP_MOVE_END 65535
#define B_TRAINER_OPPONENT_A 0
#define BATTLE_TYPE_TRAINER 1
#define MON_DATA_SPECIES 0
#define MON_DATA_LEVEL 1
#define CHAR_A 'A'
#define CHAR_a 'a'
#define CHAR_0 '0'
#define CHAR_PERIOD '.'
#define CHAR_QUESTION_MARK '?'
#define CHAR_COMMA ','
#define CHAR_SPACE ' '
#define EOS 0
#define A_BUTTON 1
#define B_BUTTON 2
#define TASK_NONE 255
#define B_OUTCOME_WON 1
#define B_OUTCOME_DREW 3
#define REMATCH_CALVIN 0
#define REMATCH_MIGUEL 1
#define REMATCH_WINSTON 2
#define REMATCH_CINDY 3
#define REMATCH_KAREN 4
#define REMATCH_JERRY 5
struct Pokemon{unsigned species,level;u16 moves[4];};
struct LevelUpMove{unsigned move,level;};
struct Move{unsigned power,pp,type,category;}gMovesInfo[MOVES_COUNT];
struct Save1{struct{int mapGroup,mapNum;}location;}save1,*gSaveBlock1Ptr=&save1;
struct Save2{u8 playerTrainerId[4];}save2,*gSaveBlock2Ptr=&save2;
void CB2_Overworld(void){}
struct{unsigned inBattle,newKeys;void(*callback2)(void);}gMain;
struct{unsigned opponentA;}params;
#define TRAINER_BATTLE_PARAM params
struct Pokemon gParties[1][6];unsigned gBattleTypeFlags=1,gBattleOutcome=1;
int gRematchTable[6];static int sent,original,battle,destroyed,hidden=1,connected=1,eligible=1;
static char line[100];static struct LevelUpMove learnset[256];
unsigned GetMonData(struct Pokemon*m,unsigned k){return k==MON_DATA_SPECIES?m->species:m->level;}
const struct LevelUpMove*GetSpeciesLevelUpLearnset(unsigned s){(void)s;return learnset;}
void SetMonMoveSlot(struct Pokemon*m,unsigned move,unsigned slot){m->moves[slot]=move;}
int ShowFieldMessage(const u8*p){(void)p;hidden=0;return 1;}
void HideFieldMessageBox(void){hidden=1;}
int IsFieldMessageBoxHidden(void){return hidden;}
int LinkTransport_RematchStrategySend(const char*p){strcpy(line,p);sent++;return connected;}
int BattleSetup_UsesKantoTutorialRules(void){return 0;}
int NativeLink_IsActive(void){return 0;}
int WorldActivity_IsEncounterPending(void){return 0;}
int TrainerIdToRematchTableId(const int*t,unsigned id){(void)t;return id==42?0:-1;}
int EligibleWorldRematch(const int*t,int id){(void)t;(void)id;return eligible;}
int DoesCurrentMapMatchRematchTrainerMap(int id,const int*t,int g,int m){(void)id;(void)t;return g==0&&m==2;}
u8 CreateTask(void(*f)(u8),unsigned n){(void)f;(void)n;return 7;}
void DestroyTask(u8 t){(void)t;destroyed++;}
int ScriptContext_IsEnabled(void){return 0;}
int ArePlayerFieldControlsLocked(void){return 0;}
static void DoTrainerBattle(void);
#include "../src/world/rematch_strategy.inc.c"
static void Strategy_Original(void){original++;}
static void DoTrainerBattle(void){battle++;
#if EW_REMATCH_STRATEGIES
Strategy_Apply();
#endif
}
int main(void){
#if EW_REMATCH_STRATEGIES
 char reply[250];char *plan[]={"RS","PLAN","1","0123456789abcdef0123456789abcdef","3","13","11","0","1"};
 save1.location.mapNum=2;params.opponentA=42;
 assert(!Strategy_Begin());
 assert(WorldRematchStrategy_Command("/world-rematches on",reply,sizeof(reply))&&sStrategy.enabled);
 assert(Strategy_Begin()&&sStrategy.phase==1);
 assert(!strcmp(line,"RS GET 1 calvin\n"));
 plan[2]="4294967297";assert(!WorldRematchStrategy_Line(9,plan));plan[2]="2";assert(!WorldRematchStrategy_Line(9,plan));plan[2]="1";
 plan[5]="10";assert(!WorldRematchStrategy_Line(9,plan));plan[5]="13";
 assert(WorldRematchStrategy_Line(9,plan));Strategy_Task(7);assert(sStrategy.shown);
 gMain.newKeys=B_BUTTON;Strategy_Task(7);assert(original==1&&battle==0&&!sStrategy.phase);
 assert(Strategy_Begin());plan[2]="2";assert(WorldRematchStrategy_Line(9,plan));Strategy_Task(7);
 learnset[0]=(struct LevelUpMove){1,1};learnset[1]=(struct LevelUpMove){2,3};learnset[2]=(struct LevelUpMove){3,6};learnset[3]=(struct LevelUpMove){4,100};learnset[4]=(struct LevelUpMove){2,3};learnset[5]=(struct LevelUpMove){LEVEL_UP_MOVE_END,0};
 gMovesInfo[1]=(struct Move){40,20,1};gMovesInfo[2]=(struct Move){0,20,13,2};gMovesInfo[3]=(struct Move){60,15,11};gMovesInfo[4]=(struct Move){200,10,13};
 gParties[0][0]=(struct Pokemon){1,10,{9,9,9,9}};
 hidden=1;gMain.newKeys=A_BUTTON;Strategy_Task(7);assert(battle==1&&sStrategy.applied);
 assert(gParties[0][0].moves[0]==2&&gParties[0][0].moves[1]==3&&gParties[0][0].moves[2]==1&&gParties[0][0].moves[3]==0);
 Strategy_Finish();assert(!strcmp(line,"RS DONE 0123456789abcdef0123456789abcdef 1\n"));
 int before=sent;Strategy_Finish();assert(sent==before);
 sStrategy.phase=4;sStrategy.applied=TRUE;gMain.callback2=CB2_Overworld;WorldRematchStrategy_Update();assert(!sStrategy.phase);Strategy_Finish();assert(sent==before);
 sStrategy.phase=4;sStrategy.applied=TRUE;gMain.inBattle=1;
 WorldRematchStrategy_Command("/world-rematches off",reply,sizeof(reply));assert(!sStrategy.enabled);Strategy_Finish();assert(sent==before);
 gMain.inBattle=0;WorldRematchStrategy_Command("/world-rematches on",reply,sizeof(reply));
 assert(Strategy_Begin());WorldRematchStrategy_Reset();Strategy_Task(7);assert(original==2&&!sStrategy.enabled&&!sStrategy.phase);
 WorldRematchStrategy_Command("/world-rematches on",reply,sizeof(reply));assert(Strategy_Begin());
 for(int i=0;i<180;i++)Strategy_Task(7);assert(original==3&&!sStrategy.phase);
 assert(Strategy_Begin());save1.location.mapNum=3;Strategy_Task(7);assert(original==3&&!sStrategy.phase);save1.location.mapNum=2;
 eligible=0;assert(!Strategy_Begin());eligible=1;gBattleTypeFlags=3;assert(!Strategy_Begin());gBattleTypeFlags=1;
 for(int i=0;i<256;i++)learnset[i]=(struct LevelUpMove){1,1};u16 out[4]={0};assert(!Strategy_Moves(&gParties[0][0],out));
 WorldRematchStrategy_Command("/world-rematches off",reply,sizeof(reply));assert(!Strategy_Begin());
#else
 char reply[100];assert(WorldRematchStrategy_Command("/world-rematches on",reply,sizeof(reply)));assert(strstr(reply,"disabled"));assert(!Strategy_Begin());Strategy_Apply();Strategy_Finish();WorldRematchStrategy_Reset();assert(!sent&&!original&&!battle);
#endif
 puts("native strategy checks passed");return 0;
}
