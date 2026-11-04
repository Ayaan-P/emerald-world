#if defined(PORTABLE) && !defined(_WIN32)
#include <string.h>
#include "gba/types.h"
#include "platform/unstuck_landing.h"
#define UNSTUCK_MAX_CELLS 8192
#define UNSTUCK_MAX_STEPS 2

/* Bounded search near a known heal point. Both grids must reflect normal,
 * symmetric walking tiles with no event/warp hazards. The start must be a
 * plain tile, but may be occupied; all subsequent cells must also be clear.
 * Select only a tile with a clear walking neighbor. This function cannot
 * establish freshness or validate world data; its caller owns those checks. */
bool8 Unstuck_SelectLanding(const u8 *plain, const u8 *clear, unsigned width, unsigned height,
                            unsigned spawnX, unsigned spawnY, s16 *outX, s16 *outY)
{
    static u8 seen[UNSTUCK_MAX_CELLS], depth[UNSTUCK_MAX_CELLS];
    static u16 queue[UNSTUCK_MAX_CELLS];
    static const s8 dx[4] = {0, 0, -1, 1}, dy[4] = {1, -1, 0, 0};
    unsigned start, head=0, tail=0;
    if (!plain || !clear || !outX || !outY || !width || !height || width > 128 || height > 128
        || width * height > UNSTUCK_MAX_CELLS || spawnX >= width || spawnY >= height) return 0;
    start = spawnX + spawnY * width;
    if (!plain[start]) return 0;
    memset(seen, 0, width * height);
    seen[start]=1; depth[start]=0; queue[tail++]=(u16)start;
    while (head < tail) {
        unsigned cell=queue[head++], x=cell % width, y=cell / width, i;
        bool8 exit=0;
        for (i=0; i<4; i++) {
            int nx=(int)x+dx[i], ny=(int)y+dy[i];
            unsigned next;
            if (nx<0 || ny<0 || (unsigned)nx>=width || (unsigned)ny>=height) continue;
            next=(unsigned)nx + (unsigned)ny * width;
            if (!plain[next] || !clear[next]) continue;
            exit=1;
            if (depth[cell] < UNSTUCK_MAX_STEPS && !seen[next]) {
                seen[next]=1; depth[next]=depth[cell]+1; queue[tail++]=(u16)next;
            }
        }
        if (plain[cell] && clear[cell] && exit) { *outX=(s16)x; *outY=(s16)y; return 1; }
    }
    return 0;
}
#endif
