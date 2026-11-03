#ifdef PORTABLE
#include "platform/native_link.h"
#include <string.h>
#include <limits.h>

/* Bounded control FIFO plus exactly one in-flight command/matrix. */
static NativeLinkEmit sEmit;
static void *sContext;
static const uint16_t *sSource;
static struct
{
    uint64_t session;
    unsigned mode, slot, open, paired, connected, advance;
    uint32_t generation, round;
    unsigned pending, sent, received, inTick, consumed, haveLast;
    uint16_t command[8], matrix[2][8], last[2][8];
} s;
static struct NativeLinkEvent sQueue[8];
static unsigned sCount;

static struct NativeLinkEvent Event(unsigned kind)
{
    struct NativeLinkEvent e;
    memset(&e, 0, sizeof(e));
    e.kind = kind; e.session = s.session; e.mode = s.mode; e.slot = s.slot;
    e.generation = s.generation;
    e.round = kind == NATIVE_LINK_COMMAND ? s.round : 0;
    return e;
}
void NativeLink_Init(NativeLinkEmit emit, void *context)
{
    memset(&s, 0, sizeof(s)); sCount = 0; sSource = 0;
    sEmit = emit; sContext = context;
}
void NativeLink_Reset(void)
{
    if (s.session) NativeLink_Abort();
    memset(&s, 0, sizeof(s));
}
int NativeLink_Admit(uint64_t session, unsigned mode, unsigned slot)
{
    if (!session || mode < NATIVE_LINK_SINGLE || mode > NATIVE_LINK_TRADE || slot > 1 || s.session || sCount || !sEmit)
        return 0;
    memset(&s, 0, sizeof(s));
    s.session = session; s.mode = mode; s.slot = slot;
    return 1;
}
int NativeLink_IsActive(void) { return s.session != 0; }
int NativeLink_IsOpen(void) { return s.session && s.open; }
int NativeLink_IsConnected(void) { return NativeLink_IsOpen() && s.connected; }
unsigned NativeLink_LocalId(void) { return s.slot; }
uint32_t NativeLink_Generation(void) { return s.generation; }
/* Engine queue counts exclude the matrix already dequeued by Main1. Keeping
 * it for echo/replay validation until AfterFrame is not a hardware backlog.
 * Close/standby callbacks require these counts to drain to zero. */
unsigned NativeLink_RecvQueueCount(void) { return s.received && !s.consumed; }
unsigned NativeLink_SendQueueCount(void) { return s.pending && !s.received; }
void NativeLink_SetCommandSource(const uint16_t send[8]) { sSource = send; }
void NativeLink_Pump(void)
{
    while (sCount && sEmit && sEmit(sContext, &sQueue[0]))
    {
        --sCount;
        memmove(sQueue, sQueue + 1, sCount * sizeof(sQueue[0]));
    }
    if (!sCount && s.pending && !s.sent && sEmit)
    {
        struct NativeLinkEvent e = Event(NATIVE_LINK_COMMAND);
        memcpy(e.command, s.command, sizeof(e.command));
        if (sEmit(sContext, &e)) s.sent = 1;
    }
}
void NativeLink_Abort(void)
{
    struct NativeLinkEvent e = Event(NATIVE_LINK_ABORT);
    /* Explicit cancellation invalidates unsent generation data. */
    memset(&s, 0, sizeof(s));
    sCount = 0;
    if (e.session) { sQueue[sCount++] = e; NativeLink_Pump(); }
}
static int Fail(void) { NativeLink_Abort(); return -1; }
static int Queue(struct NativeLinkEvent e)
{
    if (sCount == sizeof(sQueue) / sizeof(sQueue[0])) return Fail();
    sQueue[sCount++] = e; NativeLink_Pump(); return 1;
}
void NativeLink_Open(uint16_t linkType)
{
    struct NativeLinkEvent e;
    if (!s.session) return;
    if (s.open || s.generation == UINT32_MAX) { NativeLink_Abort(); return; }
    ++s.generation;
    s.round = 0; s.open = 1; s.paired = s.connected = s.advance = 0;
    s.pending = s.sent = s.received = s.inTick = s.consumed = s.haveLast = 0;
    e = Event(NATIVE_LINK_OPEN); e.linkType = linkType; Queue(e);
}
void NativeLink_Close(void)
{
    struct NativeLinkEvent e;
    if (!NativeLink_IsOpen()) return;
    e = Event(NATIVE_LINK_CLOSE);
    s.open = s.paired = s.connected = 0;
    s.pending = s.sent = s.received = s.inTick = s.consumed = 0;
    Queue(e);
}
int NativeLink_Feed(unsigned kind, uint64_t session, uint32_t generation,
                    uint32_t round, const uint16_t matrix[2][8])
{
    static const uint16_t zero[2][8] = {{0}};
    if (!s.session || session != s.session || generation < s.generation) return 0;
    if (generation != s.generation || !s.open || !matrix) return Fail();
    if (kind == NATIVE_LINK_PAIR || kind == NATIVE_LINK_HANDSHAKE)
    {
        if (round || memcmp(matrix, zero, sizeof(zero))) return Fail();
        if (kind == NATIVE_LINK_PAIR) s.paired = 1;
        else
        {
            if (!s.paired || (s.slot == 0 && !s.advance)) return Fail();
            s.connected = 1;
        }
        return 1;
    }
    if (kind != NATIVE_LINK_ROUND || !s.paired) return Fail();
    if (s.haveLast && s.round && round == s.round - 1)
        return memcmp(matrix, s.last, sizeof(s.last)) ? Fail() : 1;
    if (round != s.round || !s.pending || !s.sent) return Fail();
    if (memcmp(matrix[s.slot], s.command, sizeof(s.command))) return Fail();
    if (s.received) return memcmp(matrix, s.matrix, sizeof(s.matrix)) ? Fail() : 1;
    if (!s.connected && memcmp(matrix, zero, sizeof(zero))) return Fail();
    memcpy(s.matrix, matrix, sizeof(s.matrix)); s.received = 1;
    return 1;
}
int NativeLink_FrameReady(void)
{
    if (!s.session || !s.open || !s.paired) { NativeLink_Pump(); return 1; }
    if (!s.pending)
    {
        if (!sSource) return 0;
        if (s.round == 0)
            memset(s.command, 0, sizeof(s.command));
        else
            memcpy(s.command, sSource, sizeof(s.command));
        s.pending = 1;
    }
    NativeLink_Pump();
    return s.received != 0;
}
int NativeLink_BeforeFrame(const uint16_t send[8])
{
    if (!sSource) sSource = send;
    if (!NativeLink_FrameReady()) return 0;
    if (s.open && s.paired)
    {
        if (s.inTick) return 0;
        s.inTick = 1; s.consumed = 0;
    }
    return 1;
}
void NativeLink_AfterFrame(void)
{
    if (!s.inTick) return;
    if (!s.consumed || s.round == UINT32_MAX) { NativeLink_Abort(); return; }
    memcpy(s.last, s.matrix, sizeof(s.last)); s.haveLast = 1;
    ++s.round;
    s.pending = s.sent = s.received = s.inTick = s.consumed = 0;
}
uint32_t NativeLink_Main1(uint8_t *advance, const uint16_t send[8], uint16_t recv[5][8])
{
    uint32_t status;
    (void)send;
    memset(recv, 0, 5 * 8 * sizeof(uint16_t));
    if (!NativeLink_IsOpen()) return 0;
    if (*advance == 2)
    {
        *advance = 0;
        NativeLink_Abort();
        return 0;
    }
    status = s.slot | (s.slot == 0 ? 0x20u : 0);
    if (s.paired) status |= 2u << 2;
    if (*advance == 1 && s.paired && !s.slot && !s.advance)
    {
        s.advance = 1; Queue(Event(NATIVE_LINK_ADVANCE));
    }
    if (s.paired) *advance = 0;
    if (s.connected) status |= 0x40u;
    if (s.inTick && s.received && !s.consumed)
    {
        memcpy(recv, s.matrix, sizeof(s.matrix)); s.consumed = 1;
    }
    else if (s.paired) status |= 0x100u;
    return status;
}
#endif
