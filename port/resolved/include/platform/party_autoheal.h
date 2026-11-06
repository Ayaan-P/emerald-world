#ifndef GUARD_PLATFORM_PARTY_AUTOHEAL_H
#define GUARD_PLATFORM_PARTY_AUTOHEAL_H
#ifdef PORTABLE
#include "global.h"

enum AutoHealResult
{
    AUTO_HEAL_REFUSED,
    AUTO_HEAL_NOTHING,
    AUTO_HEAL_USED
};

/* Synchronous, game-thread-only transaction from the ordinary field Party UI.
 * Uses private bag stock only. Does not save, revive, or implement loadouts. */
bool8 WorldAutoHeal_Available(void);
enum AutoHealResult WorldAutoHeal_Run(void);
#endif
#endif
