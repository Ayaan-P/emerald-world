#ifdef PORTABLE
#include "platform/native_link.h"
#include <string.h>
#include <limits.h>

#define COMMAND_CAPACITY 50
/* Cover WAN latency without changing the engine's one-matrix-per-tick seam. */
#define ROUND_CAPACITY 16
static NativeLinkEmit sEmit;
static void *sContext;
static const uint16_t *sSource;
static struct
{
    uint64_t session, nextRound;
    unsigned mode, slot, open, paired, connected, advance;
    uint32_t generation, round;
    unsigned inTick, consumed, prepared, haveLast;
    uint16_t last[2][8];
    struct
    {
        unsigned sent, received;
        uint16_t command[8], matrix[2][8];
    } wire[ROUND_CAPACITY];
    uint16_t commands[COMMAND_CAPACITY][8];
    unsigned head, count;
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
static int Nonzero(const uint16_t *words, unsigned count)
{
    unsigned i;
    for (i = 0; i < count; ++i) if (words[i]) return 1;
    return 0;
}
unsigned NativeLink_RecvQueueCount(void)
{
    uint64_t round;
    unsigned count = 0;
    if (!s.open) return 0;
    for (round = s.round; round < s.nextRound; ++round)
    {
        unsigned index = round % ROUND_CAPACITY;
        if (round == s.round && s.consumed) continue;
        if (s.wire[index].received
            && (Nonzero(s.wire[index].matrix[0], 8) || Nonzero(s.wire[index].matrix[1], 8))) ++count;
    }
    return count;
}
unsigned NativeLink_SendQueueCount(void)
{
    uint64_t round;
    unsigned count = s.count;
    if (!s.open) return 0;
    for (round = s.round; round < s.nextRound; ++round)
    {
        unsigned index = round % ROUND_CAPACITY;
        if (!s.wire[index].received && Nonzero(s.wire[index].command, 8)) ++count;
    }
    return count;
}
void NativeLink_SetCommandSource(const uint16_t send[8]) { sSource = send; }
void NativeLink_Pump(void)
{
    uint64_t round;
    while (sCount && sEmit && sEmit(sContext, &sQueue[0]))
    {
        --sCount;
        memmove(sQueue, sQueue + 1, sCount * sizeof(sQueue[0]));
    }
    if (sCount || !s.open || !sEmit) return;
    for (round = s.round; round < s.nextRound; ++round)
    {
        unsigned index = round % ROUND_CAPACITY;
        if (!s.wire[index].sent)
        {
            struct NativeLinkEvent e = Event(NATIVE_LINK_COMMAND);
            e.round = (uint32_t)round;
            memcpy(e.command, s.wire[index].command, sizeof(e.command));
            if (!sEmit(sContext, &e)) break;
            s.wire[index].sent = 1;
        }
    }
}
void NativeLink_EndSession(uint64_t session)
{
    unsigned i, kept = 0;
    if (!session) return;
    /* Only an authoritative remote end or lost channel invalidates undelivered
     * events. Do not echo ABORT into a session the transport has already ended. */
    if (s.session == session) memset(&s, 0, sizeof(s));
    for (i = 0; i < sCount; ++i)
        if (sQueue[i].session != session) sQueue[kept++] = sQueue[i];
    sCount = kept;
}
void NativeLink_Abort(void)
{
    struct NativeLinkEvent e = Event(NATIVE_LINK_ABORT);
    if (!e.session) return; /* Keep any previously queued terminal event. */
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
    s.round = 0; s.nextRound = 0;
    s.open = 1; s.paired = s.connected = s.advance = 0;
    s.head = s.count = 0;
    s.inTick = s.consumed = s.prepared = s.haveLast = 0;
    memset(s.wire, 0, sizeof(s.wire));
    e = Event(NATIVE_LINK_OPEN); e.linkType = linkType; Queue(e);
}
int NativeLink_TryClose(void)
{
    NativeLink_Pump();
    if (sCount || NativeLink_SendQueueCount() || NativeLink_RecvQueueCount()) return 0;
    NativeLink_Close();
    return !sCount;
}
void NativeLink_Close(void)
{
    struct NativeLinkEvent e;
    if (!NativeLink_IsOpen()) return;
    e = Event(NATIVE_LINK_CLOSE);
    s.open = s.paired = s.connected = 0;
    s.head = s.count = 0;
    s.inTick = s.consumed = s.prepared = 0;
    /* Retain the bounded emitted window to validate late echoes. They cannot
     * reach the engine after close or contaminate the next generation. */
    Queue(e);
}
int NativeLink_Feed(unsigned kind, uint64_t session, uint32_t generation,
                    uint32_t round, const uint16_t matrix[2][8])
{
    static const uint16_t zero[2][8] = {{0}};
    unsigned index;
    if (!s.session || session != s.session || generation < s.generation) return 0;
    if (generation != s.generation || !matrix) return Fail();
    if (kind == NATIVE_LINK_PAIR || kind == NATIVE_LINK_HANDSHAKE)
    {
        if (!s.open || round || memcmp(matrix, zero, sizeof(zero))) return Fail();
        if (kind == NATIVE_LINK_PAIR) s.paired = 1;
        else
        {
            if (!s.paired || (s.slot == 0 && !s.advance)) return Fail();
            s.connected = 1;
        }
        return 1;
    }
    if (kind != NATIVE_LINK_ROUND) return Fail();
    if (s.haveLast && s.round && round == s.round - 1)
        return memcmp(matrix, s.last, sizeof(s.last)) ? Fail() : 1;
    if (round < s.round || (uint64_t)round >= s.nextRound) return Fail();
    index = round % ROUND_CAPACITY;
    if (!s.wire[index].sent || memcmp(matrix[s.slot], s.wire[index].command, sizeof(s.wire[index].command))) return Fail();
    if (s.wire[index].received)
        return memcmp(matrix, s.wire[index].matrix, sizeof(s.wire[index].matrix)) ? Fail() : 1;
    if (s.open && (!s.paired || (!s.connected && memcmp(matrix, zero, sizeof(zero))))) return Fail();
    memcpy(s.wire[index].matrix, matrix, sizeof(s.wire[index].matrix));
    s.wire[index].received = 1;
    return s.open ? 1 : 0;
}
int NativeLink_FrameReady(void)
{
    if (s.session && s.open && s.paired && !s.prepared
        && s.nextRound - s.round < ROUND_CAPACITY)
    {
        unsigned index;
        if (s.nextRound > UINT32_MAX) { NativeLink_Abort(); return 1; }
        index = s.nextRound % ROUND_CAPACITY;
        memset(&s.wire[index], 0, sizeof(s.wire[index]));
        if (s.nextRound && s.connected && s.count)
        {
            memcpy(s.wire[index].command, s.commands[s.head], sizeof(s.wire[index].command));
            s.head = (s.head + 1) % COMMAND_CAPACITY;
            --s.count;
        }
        ++s.nextRound;
        s.prepared = 1;
    }
    NativeLink_Pump();
    return 1;
}
int NativeLink_BeforeFrame(const uint16_t send[8])
{
    if (!sSource) sSource = send;
    if (s.inTick) return 0;
    if (s.open && s.paired)
    {
        unsigned i, sentinel = 1;
        for (i = 0; i < 8; ++i) if (send[i] != 0xefff) sentinel = 0;
        if (s.connected && !sentinel && Nonzero(send, 8))
        {
            if (NativeLink_SendQueueCount() >= COMMAND_CAPACITY)
            {
                NativeLink_Abort();
                return 1;
            }
            memcpy(s.commands[(s.head + s.count) % COMMAND_CAPACITY], send,
                   sizeof(s.commands[0]));
            ++s.count;
        }
        s.inTick = 1; s.consumed = 0;
    }
    return NativeLink_FrameReady();
}
void NativeLink_AfterFrame(void)
{
    if (!s.inTick) return;
    s.inTick = s.prepared = 0;
    if (!s.consumed) return;
    if (s.round == UINT32_MAX) { NativeLink_Abort(); return; }
    memcpy(s.last, s.wire[s.round % ROUND_CAPACITY].matrix, sizeof(s.last));
    s.haveLast = 1;
    memset(&s.wire[s.round % ROUND_CAPACITY], 0, sizeof(s.wire[0]));
    ++s.round;
    s.consumed = 0;
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
    if (s.inTick && s.round < s.nextRound && s.wire[s.round % ROUND_CAPACITY].received && !s.consumed)
    {
        memcpy(recv, s.wire[s.round % ROUND_CAPACITY].matrix, sizeof(s.wire[0].matrix));
        s.consumed = 1;
    }
    else if (s.paired) status |= 0x100u;
    return status;
}
#endif
