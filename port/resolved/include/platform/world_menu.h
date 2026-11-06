#ifndef GUARD_PLATFORM_WORLD_MENU_H
#define GUARD_PLATFORM_WORLD_MENU_H
#ifdef PORTABLE
#include "gba/types.h"
/* Explicit Start-menu handoff only. No hotkey or unsolicited invitation popup.
 * Update also runs offline so the local DexNav remains reachable. */
void WorldMenu_RequestOpen(void);
void WorldMenu_Update(void);
/* Rally FieldReady must exclude this owner. In particular, an automatic return
 * must not race a deferred Stay after our window/lock have been released. */
bool8 WorldMenu_OwnsFieldInput(void);
#endif
#endif
