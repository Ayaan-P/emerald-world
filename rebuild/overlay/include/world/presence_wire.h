#ifndef EW_PRESENCE_WIRE_H
#define EW_PRESENCE_WIRE_H
#include <stddef.h>
#include <stdint.h>
#define EW_MAX_PEERS 8
#define EW_LINE_CAP 2048
struct EwPeer {
    char name[25];
    unsigned group, map, x, y, facing, graphics, ready;
};
struct EwSnapshot {
    uint64_t revision;
    unsigned count;
    struct EwPeer peers[EW_MAX_PEERS];
};
struct EwWire {
    char own[25];
    char line[EW_LINE_CAP];
    size_t used;
    int welcomed, collecting;
    struct EwSnapshot pending, live;
};
int EwValidName(const char *name);
void EwWireInit(struct EwWire *wire, const char *own);
/* Returns zero for invalid or oversized input. A snapshot is published only
 * after its END record, never while a partial snapshot is in flight. */
int EwWireFeed(struct EwWire *wire, const char *bytes, size_t length);
#endif
