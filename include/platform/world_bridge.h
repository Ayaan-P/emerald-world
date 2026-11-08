#ifndef GUARD_PLATFORM_WORLD_BRIDGE_H
#define GUARD_PLATFORM_WORLD_BRIDGE_H
#ifdef PORTABLE
#include <stdio.h>
#include "gba/types.h"
#include "platform/world_rally.h"

/* NULL config is a strict no-op. Invalid explicit config returns FALSE.
 * Optional visible_peers 1..8 bounds locally rendered humans (default 8).
 * This is NOT world population: the authority projects an eight-peer relevance
 * window and the engine may render fewer when native NPC slots are occupied.
 * Public telemetry roster includes relevant peers even without a sprite. */
bool8 WorldBridge_Init(const char *configPath);
bool8 WorldBridge_Enabled(void);
/* Authenticated transport within the normal snapshot timeout, not feature approval. */
bool8 WorldBridge_ConnectionActive(void);
/* True only after an authenticated authority template has been validated and acknowledged. */
bool8 WorldBridge_GeneratedCaveReady(void);
struct ObjectEvent;
/* True only for a currently owned remote trainer object. */
bool8 WorldBridge_IsRemoteObject(const struct ObjectEvent *object);
/* Committed presence only; stale/disconnected snapshots are unavailable. */
struct WorldBridgePeer { char name[25]; unsigned group, num, x, y; bool8 ready; };
bool8 WorldBridge_GetPeer(unsigned index, struct WorldBridgePeer *peer);
/* Authenticated cross-map roster, independent of the eight render slots.
 * Only fresh entries are enumerated. Busy entries keep ready == FALSE. */
bool8 WorldBridge_GetTravelPeer(unsigned index, struct WorldBridgePeer *peer);
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
/* SDL-side chat never locks, scripts, pauses, or writes the native game. */
int WorldBridge_ChatCommandAllowed(const char *target, const char *text);
int WorldBridge_ChatSend(const char *target, const char *text);
/* Typed rally transport. A stale/disconnected snapshot is never returned. */
bool8 WorldBridge_RallySend(unsigned action, unsigned id, unsigned arg);
bool8 WorldBridge_RallySnapshot(struct WorldRallySnapshot *out);
unsigned WorldBridge_ChatCount(void);
const char *WorldBridge_ChatStatus(void);
void WorldBridge_ChatLine(unsigned index, char *out, unsigned size);
#endif
#endif
