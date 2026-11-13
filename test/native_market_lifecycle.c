/* Bounded wire driver around the complete production market module. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
struct {struct {unsigned mapGroup,mapNum;} location;} save,*gSaveBlock1Ptr=&save;
struct {unsigned char playerTrainerId[4];} save2,*gSaveBlock2Ptr=&save2;
static int entryReady=1;
int WorldBridge_MarketEntryReady(void){return entryReady;}
int WorldBridge_ConnectionActive(void){return 1;}
int NativeLink_IsActive(void){return 0;}
int LinkTransport_MarketSend(const char *line){fputs(line,stdout);return 1;}
#include "ACTUAL_SOURCE"
int main(void)
{
    char line[256];unsigned short items[9];
    save.location.mapGroup=9;save.location.mapNum=13;
    while(fgets(line,sizeof(line),stdin)){
        if(line[0]=='D')entryReady=0;
        else if(line[0]=='P')WorldMarket_Pump();
        else if(line[0]=='T'){for(unsigned i=0;i<120;i++)WorldMarket_Pump();}
        else if(line[0]=='S'){assert(WorldMarket_Snapshot(9,13,items)==2);assert(items[0]==43);}
        else if(line[0]=='B')assert(WorldMarket_Purchased(43,1));
        else if(line[0]=='A')assert(s.status==2);
        else if(line[0]=='L'){
            char *tokens[16],*p=strtok(line+2," \n");unsigned n=0;
            while(p){assert(n<16);tokens[n++]=p;p=strtok(NULL," \n");}
            assert(WorldMarket_Line(n,tokens));
        }else return 2;
        puts("DONE");fflush(stdout);
    }
    return 0;
}
