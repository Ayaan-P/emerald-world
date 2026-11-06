#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
bool expansion_cave_decode(const uint8_t *, unsigned long, uint16_t *);
int main(void) {
    uint8_t p[8+31*31]; uint16_t o[31*31]; memset(p,'#',sizeof p);memcpy(p,"EWGMAP01",8);
    for(int y=1;y<30;y++) p[8+y*31+1]='.';
    for(int x=1;x<30;x++) p[8+28*31+x]='.';
    p[8+29*31+29]='.';
    assert(expansion_cave_decode(p,sizeof p,o)); assert(o[32]==0x3333 && o[29*31+29]==0x3323);
    p[8+5*31+5]='.'; assert(!expansion_cave_decode(p,sizeof p,o));assert(o[32]==0x3333);
    return 0;
}
