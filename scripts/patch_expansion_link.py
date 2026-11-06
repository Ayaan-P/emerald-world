#!/usr/bin/env python3
"""Overlay Emerald World's guarded virtual-cable hooks on the pinned donor.

Do not mutate the donor checkout. Fail closed if expected upstream code changes.
Only the native adapter path changes; ordinary donor cable behavior is retained.
"""
from pathlib import Path
import sys


def replace_one(source, old, new):
    count = source.count(old)
    if count != 1:
        raise ValueError(f'expected one source anchor, found {count}: {old[:80]!r}')
    return source.replace(old, new, 1)


def replace_function(source, signature, body):
    start = source.index(signature + '\n{')
    first = source.index('{', start)
    level = 0
    for pos in range(first, len(source)):
        if source[pos] == '{': level += 1
        elif source[pos] == '}':
            level -= 1
            if level == 0:
                return source[:start] + body + source[pos + 1:]
    raise ValueError('unterminated function: ' + signature)


def generate(donor, vanilla):
    donor = replace_one(donor, '#include "constants/trade.h"', '''#include "constants/trade.h"
#define PORTABLE 1
#include "platform/native_link.h"
#undef PORTABLE''')
    donor = replace_one(donor, 'static struct BlockTransfer sBlockRecv[MAX_LINK_PLAYERS];', '''static struct BlockTransfer sBlockRecv[MAX_LINK_PLAYERS];
static bool8 sNativePlayerExchangeRequested;
static bool8 sNativeCableOpen;''')
    donor = replace_one(donor, '        ResetSerial();\n        InitLink();\n        gLinkCallback = LinkCB_RequestPlayerDataExchange;', '''        ResetSerial();
        InitLink();
        if (NativeLink_IsActive())
        {
            NativeLink_SetCommandSource(gSendCmd);
            NativeLink_Open(gLinkType);
            sNativeCableOpen = NativeLink_IsOpen();
            memset(sBlockRecv, 0, sizeof(sBlockRecv));
            sNativePlayerExchangeRequested = FALSE;
        }
        gLinkCallback = LinkCB_RequestPlayerDataExchange;''')
    donor = replace_one(donor, 'void CloseLink(void)\n{', '''void CloseLink(void)
{
    if (NativeLink_IsActive()) NativeLink_Close();
    sNativeCableOpen = FALSE;''')
    donor = replace_one(donor, 'u16 LinkMain2(const u16 *heldKeys)\n{\n    u8 i;', '''u16 LinkMain2(const u16 *heldKeys)
{
    u8 i;
    bool8 virtualSession = NativeLink_IsActive();''')
    donor = replace_one(donor, '        ProcessRecvCmds(SIO_MULTI_CNT->id);', '''        ProcessRecvCmds(virtualSession ? NativeLink_LocalId() : SIO_MULTI_CNT->id);
        if (virtualSession && (gLinkErrorOccurred || !NativeLink_IsActive())) return gLinkStatus;''')
    # Carry the existing project's validated block/command handling as a unit.
    a = vanilla.index('static void ProcessRecvCmds(u8 unused)\n{')
    b = vanilla.index('\nstatic void BuildSendCmd(', a)
    process = vanilla[a:b].replace('#ifdef PORTABLE', '#if defined(PLATFORM_NATIVE)')
    process = process.replace('gLinkDummy2 = TRUE;', '(void)0;')
    # Expansion deliberately ignores oversize blocks; native sessions reject
    # them before this branch. Avoid importing vanilla's decompression buffer.
    old = '''                    u16 *buffer;
                    u16 j;

                    buffer = (u16 *)gDecompressionBuffer;
                    for (j = 0; j < CMD_LENGTH - 1; j++)
                    {
                        buffer[(sBlockRecv[i].pos / 2) + j] = gRecvCmds[i][j + 1];
                    }'''
    process = replace_one(process, old, '                    /* Oversize blocks are rejected before reaching this path. */')
    donor = replace_function(donor, 'static void ProcessRecvCmds(u8 unused)', process)
    donor = replace_one(donor, 'static bool32 InitBlockSend(const void *src, size_t size)\n{', '''static bool32 InitBlockSend(const void *src, size_t size)
{
    if (NativeLink_IsActive() && (!size || size > BLOCK_BUFFER_SIZE || ((size + 13) / 14) * 14 > BLOCK_BUFFER_SIZE))
    {
        NativeLink_Abort(); gLinkErrorOccurred = TRUE; return FALSE;
    }''')
    donor = replace_one(donor, '        gSendCmd[i + 1] = (src[sBlockSend.pos + i * 2 + 1] << 8) | src[sBlockSend.pos + i * 2];', '''        if (NativeLink_IsActive())
        {
            size_t offset = sBlockSend.pos + i * 2;
            gSendCmd[i + 1] = offset < sBlockSend.size ? src[offset] : 0;
            if (offset + 1 < sBlockSend.size) gSendCmd[i + 1] |= src[offset + 1] << 8;
        }
        else
            gSendCmd[i + 1] = (src[sBlockSend.pos + i * 2 + 1] << 8) | src[sBlockSend.pos + i * 2];''')
    donor = replace_one(donor, '    return SIO_MULTI_CNT->id;\n}', '''    if (NativeLink_IsActive()) return NativeLink_LocalId();
    return SIO_MULTI_CNT->id;
}''')
    donor = replace_one(donor, 'bool8 GetSioMultiSI(void)\n{', '''bool8 GetSioMultiSI(void)
{
    if (NativeLink_IsActive()) return NativeLink_LocalId() != 0;''')
    donor = replace_one(donor, 'static bool8 IsSioMultiMaster(void)\n{', '''static bool8 IsSioMultiMaster(void)
{
    if (NativeLink_IsActive()) return NativeLink_LocalId() == 0;''')
    donor = replace_one(donor, 'u32 GetLinkRecvQueueLength(void)\n{', '''u32 GetLinkRecvQueueLength(void)
{
    if (NativeLink_IsActive()) return NativeLink_RecvQueueCount();''')
    donor = replace_one(donor, 'u32 LinkMain1(u8 *shouldAdvanceLinkState, u16 *sendCmd, u16 (*recvCmds)[CMD_LENGTH])\n{\n    u32 retVal;\n    u32 retVal2;', '''u32 LinkMain1(u8 *shouldAdvanceLinkState, u16 *sendCmd, u16 (*recvCmds)[CMD_LENGTH])
{
    u32 retVal;
    u32 retVal2;
    if (NativeLink_IsActive())
    {
        u32 status = NativeLink_Main1(shouldAdvanceLinkState, sendCmd, recvCmds);
        gLink.localId = NativeLink_LocalId();
        gLink.playerCount = EXTRACT_PLAYER_COUNT(status);
        gLink.isMaster = gLink.localId == 0 ? LINK_MASTER : LINK_SLAVE;
        gLink.state = NativeLink_IsConnected() ? LINK_STATE_CONN_ESTABLISHED : LINK_STATE_HANDSHAKE;
        gLink.receivedNothing = EXTRACT_RECEIVED_NOTHING(status);
        gLastSendQueueCount = NativeLink_SendQueueCount();
        gLastRecvQueueCount = NativeLink_RecvQueueCount();
        return status;
    }''')
    donor = replace_one(donor, 'void LinkVSync(void)\n{', '''void LinkVSync(void)
{
    if (NativeLink_IsActive()) return;''')
    donor = replace_one(donor, 'bool8 HandleLinkConnection(void)\n{\n    bool32 main1Failed, main2Failed;', '''bool8 HandleLinkConnection(void)
{
    bool32 main1Failed, main2Failed;
    if (sNativeCableOpen && !NativeLink_IsActive())
    {
        CloseLink(); gLinkCallback = NULL; gLinkStatus = 0;
        gLinkErrorOccurred = TRUE; return FALSE;
    }
    if (NativeLink_IsActive() && !gWirelessCommType && sLinkOpen)
    {
        NativeLink_Pump();
        if (!NativeLink_FrameReady()) return TRUE;
        gLinkStatus = LinkMain1(&gShouldAdvanceLinkState, gSendCmd, gRecvCmds);
        if (!NativeLink_IsActive())
        {
            CloseLink(); gLinkCallback = NULL; gLinkErrorOccurred = TRUE; return FALSE;
        }
        LinkMain2(&gMain.heldKeys);
        if (!NativeLink_IsActive())
        {
            CloseLink(); gLinkCallback = NULL; gLinkStatus = 0; gLinkErrorOccurred = TRUE;
        }
        return FALSE;
    }''')
    return donor


def main():
    if len(sys.argv) != 4: raise SystemExit('usage: patch_expansion_link.py DONOR WORLD_LINK OUTPUT')
    donor, vanilla, output = map(Path, sys.argv[1:])
    result = generate(donor.read_text(), vanilla.read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result)

if __name__ == '__main__': main()
