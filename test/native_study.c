#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>
typedef uint8_t bool8;typedef uint8_t u8;typedef uint16_t u16;typedef int16_t s16;
#define TRUE 1
#define FALSE 0
#define A_BUTTON 1
#define B_BUTTON 2
#define L_BUTTON 4
#define SELECT_BUTTON 8
#define NUM_SPECIES 1000
#define FLAG_GET_CAUGHT 1
#ifndef EW_BIRCH_STUDIES
#define EW_BIRCH_STUDIES 1
#endif
static struct {unsigned pending,frame,deadline;bool8 ready,shown,panelActive;const u8*hook;char run[33],world[37],action[8];u8 message[512];}sCore;
static struct {unsigned move,until,mapGroup,mapNum;bool8 admitted;char key[16],run[33];}sTutor;
static struct {struct {unsigned mapGroup,mapNum;}location;}save,*gSaveBlock1Ptr=&save;
static void CB2_Overworld(void){}
static struct {void(*callback2)(void);bool8 inBattle;}gMain;
static const u8 ProfBirch_EventScript_WorldResearch[4]={0};
static int connected,script,locked,activity,hidden,sends,lineage;static s16 px,py;static char guardSent[80];static unsigned char caught[NUM_SPECIES];
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
static unsigned SpeciesToNationalPokedexNum(unsigned s){return s==100?25:s;}
static int GetSetPokedexFlag(unsigned n,unsigned op){assert(op==FLAG_GET_CAUGHT);return caught[n];}
static const u8 *GetSpeciesName(unsigned s){static const u8 name[]={0xCA,0xC3,0xC5,0xBB,0xFF};(void)s;return name;}
static const char*WorldTutorMoveName(unsigned n){return n==102?"Mimic":n==205?"Rollout":NULL;}
static int Send(const char*a,const char*b,const char*c){assert(!strcmp(a,"STUDY")&&!strcmp(b,"birch"));strcpy(sCore.action,a);strcpy(guardSent,c);sCore.pending=42;sCore.deadline=sCore.frame+180;sends++;return 1;}
#include "../src/world/birch_study.inc.c"
static void reset(void){memset(&sCore,0,sizeof(sCore));BirchStudy_Reset();memset(&sTutor,0,sizeof(sTutor));memset(caught,0,sizeof(caught));connected=lineage=1;script=locked=1;activity=sends=0;px=5;py=8;save.location.mapGroup=1;save.location.mapNum=4;hidden=0;gMain.callback2=CB2_Overworld;gMain.inBattle=0;sCore.ready=sCore.shown=1;sCore.hook=ProfBirch_EventScript_WorldResearch+2;strcpy(sCore.run,"saveA");strcpy(sCore.world,"worldA");}
#if EW_BIRCH_STUDIES
static char token[]="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
static void open(void){assert(BirchStudy_Input(L_BUTTON));assert(sStudy.stage==1);assert(!strcmp(guardSent,"view"));}
static int reply(char*mode,char*move,char*one,char*two){char*t[]={"CORE","REPLY","42","saveA","STUDY","birch",mode,move,token,"1440","2",one,two};int ok=BirchStudy_Line(13,t);if(ok)sCore.pending=0;return ok;}
static void primary(void){sStudy.page=sStudy.count+1;sStudy.shown=1;hidden=1;BirchStudy_Input(0);BirchStudy_Input(A_BUTTON);}
#endif
int main(void){
#if EW_BIRCH_STUDIES
 reset();open();assert(reply("offer","102","25","133"));assert(BirchStudy_Frame());primary();assert(!strncmp(guardSent,"accept:",7));assert(reply("active","102","25","133"));primary();assert(sends==2&&!sTutor.admitted);caught[25]=caught[133]=1;primary();assert(!strncmp(guardSent,"tutor:",6));assert(reply("teach","102","25","133"));assert(sStudy.stage==4);BirchStudy_Update();assert(!sTutor.admitted);script=locked=0;BirchStudy_Update();assert(sTutor.admitted&&sTutor.move==102&&!strcmp(sTutor.run,"saveA"));assert(!sStudy.stage);
 reset();open();assert(!reply("offer","102","25","100"));assert(!reply("offer","102","25","1000"));assert(!reply("offer","999","25","133"));assert(!reply("teach","102","25","133"));
 reset();open();assert(reply("active","102","25","133"));caught[25]=caught[133]=1;primary();assert(!reply("teach","205","25","133"));assert(!reply("teach","102","25","1"));caught[133]=0;assert(!reply("teach","102","25","133"));
 reset();open();assert(reply("active","102","25","133"));caught[25]=caught[133]=1;primary();assert(reply("teach","102","25","133"));px++;script=locked=0;BirchStudy_Update();assert(!sTutor.admitted&&!sStudy.stage);
 reset();open();strcpy(sCore.run,"saveB");assert(!reply("active","102","25","133"));BirchStudy_Update();assert(!sStudy.stage);
 reset();open();BirchStudy_Input(0);BirchStudy_Input(B_BUTTON);assert(!sCore.pending&&!sStudy.stage);assert(!reply("active","102","25","133"));
 reset();open();sCore.frame=18000;BirchStudy_Update();assert(!sStudy.stage&&!sCore.pending);
 reset();open();connected=0;BirchStudy_Update();assert(!sStudy.stage&&!sTutor.admitted);
 reset();open();assert(reply("active","102","25","133"));caught[25]=caught[133]=1;primary();assert(reply("teach","102","25","133"));caught[25]=0;script=locked=0;BirchStudy_Update();assert(!sTutor.admitted);
#else
 reset();assert(!BirchStudy_Input(L_BUTTON));assert(!BirchStudy_Frame());assert(!BirchStudy_OwnsInput());BirchStudy_Update();assert(!sends&&!sTutor.admitted);
#endif
 puts("native study checks passed");return 0;}
