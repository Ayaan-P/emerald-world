#!/usr/bin/env python3
"""Enable a file-only, synthetic peer test in a disposable native checkout.

The production overlay remains unchanged. No sockets or server are involved.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/world/presence.c'
s=p.read_text()
needle='void EwPresenceTick(void)\n{\n'
assert s.count(needle)==1
helper=r'''
/* Only in the disposable smoke-test build: exercise the actual snapshot parser,
 * sprite creation, positioning and map lifecycle without a network connection. */
static void EwTestPresence(void)
{
    static int initialized, showed, cleared;
    char snapshot[256];
    unsigned group, map, x, y;
    struct ObjectEvent *player;
    if (!initialized) {
        memset(&sPresence, 0, sizeof(sPresence));
        sPresence.initialized=1; sPresence.enabled=1; sPresence.fd=99;
        EwWireInit(&sPresence.wire, "Alice");
        if (!EwWireFeed(&sPresence.wire, "WELCOME 1 Alice 1\n", 18)) abort();
        initialized=1;
    }
    if (!field_ready()) {
        int had = sPresence.remote[0].name[0] != 0;
        clear_remotes();
        if (had && !cleared) { fprintf(stderr, "EW_TEST_PRESENCE_CLEARED\n"); cleared=1; }
        return;
    }
    player=&gObjectEvents[gPlayerAvatar.objectEventId];
    group=gSaveBlock1Ptr->location.mapGroup; map=gSaveBlock1Ptr->location.mapNum;
    x=player->currentCoords.x-MAP_OFFSET; y=player->currentCoords.y-MAP_OFFSET;
    if (x>=1023 || y>=1023) return;
    snprintf(snapshot,sizeof(snapshot),"BEGIN 1\nPEER Bob %u %u %u %u 1 %u 1\nEND\n",
             group,map,x+1,y,OBJ_EVENT_GFX_MAY_NORMAL);
    if (!EwWireFeed(&sPresence.wire,snapshot,strlen(snapshot))) abort();
    render();
    if (!showed && owned(&sPresence.remote[0])) {
        fprintf(stderr,"EW_TEST_PRESENCE_SPAWNED\n"); showed=1;
    }
}
'''
s=s.replace(needle,helper+needle+'    if (getenv("EW_TEST_PRESENCE")) { EwTestPresence(); return; }\n')
# Test-only fake descriptor must never be closed.
s=s.replace('    if (sPresence.initialized && sPresence.enabled) disconnect_world();','    if (getenv("EW_TEST_PRESENCE")) sPresence.fd=-1;\n    if (sPresence.initialized && sPresence.enabled) disconnect_world();')
p.write_text(s)
