#include "world/presence_wire.h"
#include <assert.h>
#include <string.h>
static int feed(struct EwWire *w,const char *s){return EwWireFeed(w,s,strlen(s));}
int main(void)
{
    struct EwWire w; const char *msg="WELCOME 1 Alice 1\nBEGIN 2\nPEER Bob 0 9 5 6 2 7 1\nEND\n";
    EwWireInit(&w,"Alice");
    for(size_t i=0;i<strlen(msg);i++) assert(EwWireFeed(&w,msg+i,1));
    assert(w.welcomed && w.live.count==1 && w.live.revision==2);
    assert(!strcmp(w.live.peers[0].name,"Bob") && w.live.peers[0].x==5);
    assert(feed(&w,"BEGIN 3\nPEER Carol 0 9 8 7 4 7 0\n"));
    assert(w.live.count==1 && !strcmp(w.live.peers[0].name,"Bob"));
    assert(feed(&w,"END\n") && !strcmp(w.live.peers[0].name,"Carol"));
    assert(feed(&w,"BEGIN 4\nPEER Bob 0 9 1 2 1 7 1\n"));
    assert(!feed(&w,"PEER Bob 0 9 1 2 1 7 1\n"));
    assert(w.live.revision==3 && !strcmp(w.live.peers[0].name,"Carol"));
    EwWireInit(&w,"Alice");assert(!feed(&w,"WELCOME 1 Mallory 1\n"));
    EwWireInit(&w,"Alice");assert(feed(&w,"WELCOME 1 Alice 1\nBEGIN 1\n"));
    assert(!feed(&w,"PEER Bob 0 9 1 2 5 7 1\n"));
    EwWireInit(&w,"Alice");char big[EW_LINE_CAP+1];memset(big,'a',sizeof(big));assert(!EwWireFeed(&w,big,sizeof(big)));
    return 0;
}
