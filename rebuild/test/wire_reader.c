#include "world/presence_wire.h"
#include <stdio.h>
int main(void)
{
    struct EwWire w; char chunk[7]; size_t n;
    EwWireInit(&w,"Alice");
    while ((n=fread(chunk,1,sizeof(chunk),stdin))!=0)
        if (!EwWireFeed(&w,chunk,n)) return 2;
    if (ferror(stdin) || !w.welcomed || w.collecting || w.used) return 3;
    printf("%u",w.live.count);
    if (w.live.count) printf(" %s %u %u",w.live.peers[0].name,w.live.peers[0].x,w.live.peers[0].y);
    putchar('\n');return 0;
}
