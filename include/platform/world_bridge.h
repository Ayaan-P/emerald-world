#ifndef GUARD_PLATFORM_WORLD_BRIDGE_H
#define GUARD_PLATFORM_WORLD_BRIDGE_H
#ifdef PORTABLE
#include <stdio.h>
#include "gba/types.h"

/* NULL config is a strict no-op. Invalid explicit config returns FALSE. */
bool8 WorldBridge_Init(const char *configPath);
bool8 WorldBridge_Enabled(void);
/* Copied committed presence, never mutable engine objects or credentials.
 * Index counts human peers only. Stale/disconnected snapshots return FALSE. */
struct WorldBridgePeer { char name[25]; unsigned group, num, x, y; bool8 ready; };
bool8 WorldBridge_GetPeer(unsigned index, struct WorldBridgePeer *peer);
bool8 WorldBridge_TravelTileClear(unsigned group, unsigned num, unsigned x, unsigned y);
/* Validated local identity for window labels; never returns credentials. */
const char *WorldBridge_TrainerName(void);
/* Pump sockets while a native link tick waits, without mutating engine state. */
void WorldBridge_Poll(bool8 headless);
/* Call on the game thread immediately before and after RunMainLoop. */
void WorldBridge_BeforeFrame(u32 frame, bool8 headless);
void WorldBridge_AfterFrame(u32 frame);
/* Preserve ordinary NPC/menu input. A facing owned trainer queues a fixed
 * cooperative signal. Only its committed server snapshot opens native text.
 * Shared NPCs retain their bounded literal dialogue and INTERACT event. */
u16 WorldBridge_FilterInput(u16 keys);
void WorldBridge_WriteJSON(FILE *file, u32 frame);
/* Call before SaveObjectEvents and SaveMapView to keep transient network
 * objects and tiles out of persisted saves. Reapplied at the next frame. */
void WorldBridge_PrepareSave(void);
void WorldBridge_Close(void);
#endif
#endif
