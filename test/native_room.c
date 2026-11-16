#include <assert.h>
#include <stdio.h>
#include <string.h>
static int available=1,sends;static char sent[400];
int WorldNeighborhood_Room(char *out){memset(out,'a',64);out[64]=0;return available;}
int WorldNeighborhood_Export(char *out){(void)out;return 0;}
unsigned WorldNeighborhood_Import(const char *data){(void)data;return 0;}
int LinkTransport_NeighborhoodSend(const char *line){strcpy(sent,line);sends++;return 1;}
#include "ACTUAL_SOURCE"
int main(void){char hint[256];unsigned before;char seq[20];char *ack[]={"B","ROOM",seq,"1"};
 WorldNeighborhood_Reset();assert(WorldNeighborhood_Command("/neighborhood meet on",hint,sizeof(hint)));WorldNeighborhood_Pump();
#if EW_SHARED_BASE_ROOMS
 assert(strstr(sent,"B ROOM 1 "));snprintf(seq,sizeof(seq),"%u",room.seq);assert(WorldNeighborhood_Line(4,ack));assert(room.status==1);
 before=sends;WorldNeighborhood_Pump();assert(sends==before);available=0;WorldNeighborhood_Pump();assert(strstr(sent,"B LEAVE"));assert(!room.seq);assert(!WorldNeighborhood_Line(4,ack));assert(room.status==2);
 available=1;WorldNeighborhood_Pump();assert(strstr(sent,"B ROOM"));WorldNeighborhood_Command("/neighborhood meet off",hint,sizeof(hint));assert(!room.on);assert(strstr(sent,"B LEAVE"));
 WorldNeighborhood_Command("/neighborhood meet on",hint,sizeof(hint));WorldNeighborhood_Reset();before=sends;WorldNeighborhood_Pump();assert(sends==before);
#else
 assert(!sends);assert(strstr(hint,"not enabled"));
#endif
 return 0;}
