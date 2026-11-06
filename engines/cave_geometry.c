/* Inert subset of Emerald World's EWGMAP01 cave geometry. Bounded geometry only. */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#define SIDE 31
#define CELLS (SIDE * SIDE)
#define FLOOR 0x3333u
#define WALL 0x0722u
#define EXIT 0x3323u
/* Commit only after the entire source is validated; a failed update leaves the
 * active map unchanged. Edges are walls, every floor reachable from entry. */
bool expansion_cave_decode(const uint8_t *bytes, size_t length, uint16_t *out)
{
    uint8_t seen[CELLS] = {0}; uint16_t queue[CELLS], candidate[CELLS];
    unsigned head = 0, tail = 0;
    if (!bytes || !out || length != 8 + CELLS || memcmp(bytes, "EWGMAP01", 8)) return false;
    const uint8_t *cells = bytes + 8;
    for (unsigned i=0; i<CELLS; i++) {
        unsigned x=i%SIDE, y=i/SIDE;
        if (cells[i]!='.' && cells[i]!='#') return false;
        if ((!x || !y || x==SIDE-1 || y==SIDE-1) && cells[i]!='#') return false;
        candidate[i] = cells[i]=='.' ? FLOOR : WALL;
    }
    if (cells[SIDE+1]!='.' || cells[28*SIDE+29]!='.' || cells[29*SIDE+29]!='.') return false;
    queue[tail++]=SIDE+1; seen[SIDE+1]=1;
    while (head<tail) {
        unsigned pos=queue[head++]; int neighbors[4]={(int)pos-SIDE,(int)pos+1,(int)pos+SIDE,(int)pos-1};
        for (unsigned j=0;j<4;j++) {int n=neighbors[j]; if(n>=0 && n<CELLS && cells[n]=='.' && !seen[n]) {seen[n]=1;queue[tail++]=n;}}
    }
    for (unsigned i=0;i<CELLS;i++) if(cells[i]=='.' && !seen[i]) return false;
    candidate[29*SIDE+29]=EXIT;
    memcpy(out,candidate,sizeof candidate);
    return true;
}
