#include <assert.h>
#include <stdio.h>
#include <string.h>
struct{struct{unsigned mapGroup,mapNum;}location;}save,*gSaveBlock1Ptr=&save;
struct{unsigned char playerTrainerId[4];}save2,*gSaveBlock2Ptr=&save2;
static unsigned sends;static char sent[100];static int connected=1,link;
int WorldBridge_ConnectionActive(void){return connected;}int NativeLink_IsActive(void){return link;}
int LinkTransport_MarketSend(const char*l){strcpy(sent,l);sends++;return connected;}
#include "ACTUAL_SOURCE"
int main(void){unsigned short items[9];char hint[220];save.location.mapGroup=9;save.location.mapNum=13;
 char*a[]={"MK","SHELF2","9","13","15","2","7","43","114"};
#if EW_MARKET_REACTIONS
 assert(WorldMarket_Line(9,a));assert(WorldMarket_Snapshot(9,13,items)==2);assert(WorldMarket_Purchased(43,3));assert(!strcmp(sent,"MK BUY 1 7 43 3\n"));
 char*ack[]={"MK","RECORDED","1"};assert(WorldMarket_Line(3,ack));WorldMarket_Command("/market status",hint,sizeof(hint));assert(strstr(hint,"acknowledged"));
 /* Future shelf publication may not change this open checkout's revision. */
 a[6]="8";a[7]="28";assert(WorldMarket_Line(9,a));assert(WorldMarket_Purchased(43,2));assert(!strcmp(sent,"MK BUY 2 7 43 2\n"));assert(!WorldMarket_Purchased(28,1));
 assert(!WorldMarket_Purchased(43,0));assert(!WorldMarket_Purchased(43,10000));save2.playerTrainerId[0]++;assert(!WorldMarket_Purchased(43,1));save2.playerTrainerId[0]--;save.location.mapNum++;assert(!WorldMarket_Purchased(43,1));save.location.mapNum--;link=1;assert(!WorldMarket_Purchased(43,1));link=0;
 WorldMarket_EndVisit();assert(!WorldMarket_Purchased(43,1));assert(WorldMarket_Snapshot(9,13,items)==2);assert(WorldMarket_Purchased(28,1));WorldMarket_Reset();assert(!WorldMarket_Purchased(28,1));
 a[6]="42949672960";assert(!WorldMarket_Line(9,a));
#else
 assert(!WorldMarket_Line(9,a));assert(!WorldMarket_Purchased(43,1));
#endif
 char*legacy[]={"MK","SHELF","9","13","15","1","43"};assert(WorldMarket_Line(7,legacy));assert(WorldMarket_Snapshot(9,13,items)==1);assert(!WorldMarket_Purchased(43,1));WorldMarket_Pump();assert(!strcmp(sent,EW_MARKET_REACTIONS?"MK GET 2\n":"MK GET 1\n"));return 0;}
