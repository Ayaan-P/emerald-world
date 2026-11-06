#ifdef PORTABLE
#include "platform/world_rules.h"
#include "platform/mega_game.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

static u32 sMask;
static char sWire[96];
static bool8 sInitialized;

bool8 WorldRules_Init(const char *descriptor)
{
    const char *p;
    char *end;
    unsigned long version, mask;
    unsigned i;
    if (sInitialized || !descriptor || strlen(descriptor) >= sizeof(sWire)) return 0;
    p = descriptor;
    if (*p < '1' || *p > '9') return 0;
    version = strtoul(p, &end, 10);
    if (*end != ':' || version > 2147483647ul) return 0;
    p = end + 1;
    if (*p < '0' || *p > '9') return 0;
    mask = strtoul(p, &end, 10);
    /* A proof build explicitly opts in at compile time; ordinary builds
     * reject Mega policy until the shared release guard is proven. */
    {
        const unsigned long supported = WORLD_RULE_PARTY_EXP | WORLD_RULE_REUSABLE_TMS
            | WORLD_RULE_MODERN_SPLIT | WORLD_RULE_EXPANDED_ROSTER
            | (MEGA_FEATURE_READY ? WORLD_RULE_MEGA_EVOLUTION : 0u);
        if (*end != ':' || (mask & ~supported)) return 0;
    }
    p = end + 1;
    if (strlen(p) != 64) return 0;
    for (i = 0; i < 64; i++)
        if (!((p[i] >= '0' && p[i] <= '9') || (p[i] >= 'a' && p[i] <= 'f'))) return 0;
    snprintf(sWire, sizeof(sWire), "%lu:%lu:%s", version, mask, p);
    if (strcmp(sWire, descriptor)) { sWire[0] = 0; return 0; }
    sMask = mask;
    sInitialized = 1;
    return 1;
}

bool8 WorldRules_Enabled(u32 rule) { return rule && (sMask & rule) == rule; }
u32 WorldRules_Mask(void) { return sMask; }
const char *WorldRules_Wire(void) { return sWire; }
#endif
