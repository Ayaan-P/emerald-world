#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
typedef uint8_t bool8;typedef uint16_t u16;typedef int16_t s16;typedef uint8_t u8;
#define TRUE 1
#define FALSE 0
#ifndef EW_WALLY_INVITATION
#define EW_WALLY_INVITATION 1
#endif
#define A_BUTTON 1
#define B_BUTTON 2
#define L_BUTTON 4
static struct {unsigned stage;} dummy;
static struct {unsigned pending,frame,deadline,retryAt,rematchPending,rematchStatus;bool8 ready,shown,panelActive;const u8*hook;char run[33],world[37],action[8];u8 message[512];}sCore;
static struct {struct {unsigned mapGroup,mapNum;}location;} save,*gSaveBlock1Ptr=&save;
static void CB2_Overworld(void){}
static void Other(void){}
static struct {void(*callback2)(void);bool8 inBattle;}gMain;
static const u8 VictoryRoad_1F_EventScript_WallyConversation[4]={0};
static int connected,script,locked,activity,hidden,eligible,applies,sends,sendOK,lineage;static s16 px,py;
static void PlayerGetDestCoords(s16*x,s16*y){*x=px;*y=py;}
static int WorldBridge_ConnectionActive(void){return connected;}
static int Lineage(void){return lineage;}
static int WorldActivity_OwnsFieldInput(void){return activity;}
static int WorldCastScene_OwnsInput(void){return 0;}
static int ScriptContext_IsEnabled(void){return script;}
static int ArePlayerFieldControlsLocked(void){return locked;}
static int IsFieldMessageBoxHidden(void){return hidden;}
static void HideFieldMessageBox(void){hidden=1;}
static int ShowFieldMessage(const u8*p){(void)p;hidden=0;return 1;}
static void Encode(const char*p){snprintf((char*)sCore.message,sizeof(sCore.message),"%s",p);}
static int BattleSetup_WallyRematchReady(int apply){if(!eligible||script||locked)return 0;if(apply)applies++;return 1;}
static int Send(const char*a,const char*b,const char*c){assert(!script&&!locked);assert(!strcmp(a,"REMATCH")&&!strcmp(b,"wally")&&!strcmp(c,"confirm"));sends++;if(!sendOK)return 0;strcpy(sCore.action,a);sCore.pending=42;sCore.deadline=sCore.frame+180;return 1;}
#include "../src/world/wally_invitation.inc.c"
static void reset(void){memset(&sCore,0,sizeof(sCore));WallyInvitation_Reset();connected=lineage=eligible=sendOK=1;script=locked=1;activity=applies=sends=0;px=5;py=8;save.location.mapGroup=2;save.location.mapNum=3;hidden=0;gMain.callback2=CB2_Overworld;gMain.inBattle=0;sCore.ready=sCore.shown=1;sCore.hook=VictoryRoad_1F_EventScript_WallyConversation+2;strcpy(sCore.run,"saveA");strcpy(sCore.world,"worldA");}
#if EW_WALLY_INVITATION
static void choose(void){assert(WallyInvitation_Input(L_BUTTON));assert(WallyInvitation_Frame());WallyInvitation_Input(0);hidden=1;assert(WallyInvitation_Input(A_BUTTON));assert(sWallyInvitation.stage==2);}
#endif
int main(void){
#if EW_WALLY_INVITATION
 reset();choose();WallyInvitation_Update();assert(!sends&&!applies);script=locked=0;WallyInvitation_Update();assert(sends==1&&WallyInvitation_Pending());sCore.pending=0;sCore.rematchPending=120;WallyInvitation_Update();assert(applies==1&&!sWallyInvitation.stage);WallyInvitation_Update();assert(applies==1);
 reset();WallyInvitation_Input(L_BUTTON);WallyInvitation_Frame();WallyInvitation_Input(0);WallyInvitation_Input(B_BUTTON);script=locked=0;WallyInvitation_Update();assert(!sends&&!applies);
 reset();choose();px++;script=locked=0;WallyInvitation_Update();assert(!sends&&!applies&&!sWallyInvitation.stage);
 reset();choose();strcpy(sCore.run,"saveB");script=locked=0;WallyInvitation_Update();assert(!sends&&!applies);
 reset();choose();sCore.frame=3600;WallyInvitation_Update();assert(!sends&&!applies);
 reset();choose();script=locked=0;eligible=0;WallyInvitation_Update();assert(!sends&&!applies);
 reset();choose();script=locked=0;WallyInvitation_Update();connected=0;sCore.rematchPending=120;WallyInvitation_Update();assert(!applies&&!sCore.pending&&!sCore.rematchPending);
 reset();choose();script=locked=0;WallyInvitation_Update();sCore.pending=0;WallyInvitation_Update();assert(!applies&&!sWallyInvitation.stage);
 reset();choose();script=locked=0;WallyInvitation_Update();sCore.frame=181;WallyInvitation_Update();assert(!applies&&!sCore.pending);
 reset();choose();script=locked=0;WallyInvitation_Update();eligible=0;sCore.pending=0;sCore.rematchPending=120;WallyInvitation_Update();assert(!applies);
 reset();choose();script=locked=0;WallyInvitation_Update();script=1;sCore.pending=0;sCore.rematchPending=120;WallyInvitation_Update();assert(!applies&&WallyInvitation_Pending());script=0;sCore.frame=121;WallyInvitation_Update();assert(!applies&&!sWallyInvitation.stage);
 reset();choose();WallyInvitation_Reset();script=locked=0;WallyInvitation_Update();assert(!sends&&!applies);
#else
 reset();assert(!WallyInvitation_Input(L_BUTTON));assert(!WallyInvitation_Frame());assert(!WallyInvitation_Pending());WallyInvitation_Update();assert(!sends&&!applies);
#endif
 puts("native invitation checks passed");return 0;}
