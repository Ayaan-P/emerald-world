#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char u8,bool8;typedef short s16;typedef unsigned short u16;
#define TRUE 1
#define FALSE 0
#define PARTY_SIZE 6
#define B_TRAINER_PLAYER 0
#define TASK_NONE 255
#define MAP_OFFSET 7
#define MOVE_CUT 15
#define METATILE_General_TallGrass 13
#define METATILE_General_Grass 1
enum{MON_DATA_SPECIES,MON_DATA_IS_EGG,MON_DATA_HP,MON_DATA_PERSONALITY,MON_DATA_OT_ID,MON_DATA_MOVE1};
struct Pokemon {unsigned fields[10];}gParties[1][6];
struct {u8 playerTrainerId[4];}save,*gSaveBlock2Ptr=&save;
struct {bool8 inBattle;}gMain;
static unsigned enabled=1,restores,sends,destroyed,locked;static char sent[300],notice[300];
static unsigned GetMonData(struct Pokemon *p,unsigned field){return p->fields[field];}
static bool8 GeneratedMap_CutSnapshot(char *id,char *terrain){memset(id,'a',64);id[64]=0;memset(terrain,'b',64);terrain[64]=0;return enabled;}
static void GeneratedMap_RestoreCutCell(const char *id,u8 x,u8 y){assert(x==11&&y==10);restores++;}
static void WorldPlayerCut_Notice(const char *s){snprintf(notice,sizeof(notice),"%s",s);}
static u8 CreateTask(void(*fn)(u8),unsigned priority){return 1;}
static void DestroyTask(u8 task){destroyed++;}
static int ScriptContext_IsEnabled(void){return 0;}
static int ArePlayerFieldControlsLocked(void){return locked;}
static void PlayerGetDestCoords(s16*x,s16*y){*x=17;*y=17;}
static unsigned MapGridGetMetatileIdAt(s16 x,s16 y){return 1;}
static int LinkTransport_PlayerCutSend(const char*s){sends++;strcpy(sent,s);return 1;}
#include "NATIVE_INCLUDE"
int main(void){char reply[300];
#if EW_PERSISTENT_CUT
 gParties[0][0].fields[MON_DATA_SPECIES]=1;gParties[0][0].fields[MON_DATA_HP]=20;gParties[0][0].fields[MON_DATA_MOVE1]=MOVE_CUT;
 WorldPlayerCut_Command("/shared-grass on",reply,sizeof(reply));
 PlayerCut_Begin(0);PlayerCut_Cell(18,17,13);PlayerCut_Task(1);assert(!sends&&!restores);PlayerCut_Finish();assert(sends==1&&strstr(sent,"0a0a 0b0a"));
 char nonce[16];snprintf(nonce,sizeof(nonce),"%u",sPlayerCut.nonce);char *ack[]={"PG","COMMITTED",nonce,"1"};WorldPlayerCut_Line(4,ack);PlayerCut_Task(1);assert(restores==1&&destroyed==1&&!sPlayerCut.phase);
 PlayerCut_Begin(0);PlayerCut_Cell(18,17,13);WorldPlayerCut_Reset();PlayerCut_Finish();PlayerCut_Task(1);assert(sends==1&&restores==2);
 WorldPlayerCut_Command("/shared-grass on",reply,sizeof(reply));gParties[0][0].fields[MON_DATA_MOVE1]=0;PlayerCut_Begin(0);assert(!sPlayerCut.phase);
 gParties[0][0].fields[MON_DATA_MOVE1]=MOVE_CUT;PlayerCut_Begin(0);PlayerCut_Cell(18,17,13);PlayerCut_Finish();enabled=0;PlayerCut_Task(1);assert(restores==2);enabled=1;
 PlayerCut_Begin(0);PlayerCut_Cell(18,17,13);PlayerCut_Finish();for(unsigned i=0;i<601;i++)if(sPlayerCut.phase)PlayerCut_Task(1);assert(restores==3&&strstr(notice,"unconfirmed"));
#else
 PlayerCut_Begin(0);PlayerCut_Cell(18,17,13);PlayerCut_Finish();assert(!sends&&!restores);WorldPlayerCut_Command("/shared-grass on",reply,sizeof(reply));assert(strstr(reply,"disabled"));
#endif
 return 0;}
