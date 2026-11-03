#ifndef GUARD_PLATFORM_NATIVE_LINK_H
#define GUARD_PLATFORM_NATIVE_LINK_H
#ifdef PORTABLE
#include <stdint.h>

/* All callbacks are synchronous, single-threaded and must not reenter Feed.
 * A false emit means retry, not success: the adapter retains the exact event.
 * No credentials. */
enum NativeLinkMode { NATIVE_LINK_SINGLE = 1, NATIVE_LINK_DOUBLE, NATIVE_LINK_TRADE };
enum NativeLinkEventKind { NATIVE_LINK_OPEN = 1, NATIVE_LINK_CLOSE, NATIVE_LINK_ADVANCE, NATIVE_LINK_COMMAND, NATIVE_LINK_ABORT };
enum NativeLinkCommitKind { NATIVE_LINK_PAIR = 1, NATIVE_LINK_HANDSHAKE, NATIVE_LINK_ROUND };
struct NativeLinkEvent
{
    unsigned kind, mode, slot;
    uint64_t session;
    uint32_t generation, round;
    uint16_t linkType, command[8];
};
typedef int (*NativeLinkEmit)(void *, const struct NativeLinkEvent *);
void NativeLink_Init(NativeLinkEmit emit, void *context);
/* Called ONLY after bilateral consent; session must be nonzero. */
int NativeLink_Admit(uint64_t session, unsigned mode, unsigned slot);
void NativeLink_Reset(void); /* invalidates reservation, retains transport */
void NativeLink_Abort(void); /* local cancellation, retries ABORT until emitted */
/* Transport-only authoritative invalidation. Drop only this ended session's
 * state/events, without echoing ABORT. Never use for a successful cable close. */
void NativeLink_EndSession(uint64_t session);
int NativeLink_IsActive(void);
int NativeLink_IsOpen(void);
int NativeLink_IsConnected(void);
unsigned NativeLink_LocalId(void);
uint32_t NativeLink_Generation(void);
unsigned NativeLink_RecvQueueCount(void);
unsigned NativeLink_SendQueueCount(void);
void NativeLink_Open(uint16_t linkType);
/* Graceful close: retry once per tick while the engine keeps running. Returns
 * 0 without dropping queued commands/receives, 1 after CLOSE is emitted. Caller
 * must first stop producing commands and capture its final gSendCmd via the
 * usual BeforeFrame seam. Reservation survives until remote session end. */
int NativeLink_TryClose(void);
/* Immediate hardware teardown, explicitly cancels unconsumed commands. Keeps
 * reservation for reopen. Use TryClose, not this, for a successful drain. */
void NativeLink_Close(void);
void NativeLink_Pump(void); /* retries retained transport events */
/* PAIR only after both OPEN; HANDSHAKE only after host ADVANCE.
 * Both control commits use round=0 and an all-zero matrix. ROUND always has
 * exactly 2x8 words including self echo. Returns 1 accepted/idempotent,
 * 0 stale/no session, -1 protocol error (aborts). */
int NativeLink_Feed(unsigned kind, uint64_t session, uint32_t generation,
                    uint32_t round, const uint16_t matrix[2][8]);
/* Pump IO, then BeforeFrame exactly once before input/VBlank/full tick.
 * BeforeFrame captures prior gSendCmd before LinkMain2 clears it, retaining up
 * to 50 nonzero commands including the outstanding window. Overflow aborts.
 * FrameReady prepares at most one contribution per engine tick. Repeated polls
 * never capture or add contributions. Up to 16 emitted rounds cover WAN latency;
 * each exact self echo is validated before ordered delivery to the engine.
 * The host must support the same bounded pipeline, with unchanged wire framing.
 * Network waits do not gate engine ticks. LinkMain2 must run even when Main1
 * reports RECEIVED_NOTHING, clearing send before generating the next command.
 * AfterFrame retires a wire slot only after Main1 consumes its valid matrix.
 * Idle zero rounds are not hardware queue backlog. Close retains only the
 * bounded emitted window for validation, never delivery, of late old echoes. */
int NativeLink_FrameReady(void);
void NativeLink_SetCommandSource(const uint16_t send[8]); /* call once with gSendCmd */
int NativeLink_BeforeFrame(const uint16_t send[8]);
void NativeLink_AfterFrame(void);
/* Called by LinkMain1, never clears send. Installs all five receive rows. */
uint32_t NativeLink_Main1(uint8_t *advance, const uint16_t send[8], uint16_t recv[5][8]);
#endif
#endif
