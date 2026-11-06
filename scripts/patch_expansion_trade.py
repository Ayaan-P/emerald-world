#!/usr/bin/env python3
"""Port validated native trade receive/consent guards to the pinned donor.

This overlay is disabled for gameplay until trade is explicitly integrated.
The donor remains unmodified; changed source anchors abort the build.
"""
from pathlib import Path
import sys


def one(source, old, new, expected=1):
    count = source.count(old)
    if count != expected:
        raise ValueError(f'expected {expected} source anchors, found {count}: {old[:70]!r}')
    return source.replace(old, new)


def extract_function(source, signature):
    start = source.index(signature + '\n{')
    opening = source.index('{', start)
    depth = 0
    for pos in range(opening, len(source)):
        if source[pos] == '{': depth += 1
        elif source[pos] == '}':
            depth -= 1
            if depth == 0: return source[start:pos + 1]
    raise ValueError('unterminated function: ' + signature)


def generate(donor, vanilla):
    donor = one(donor, '#include "constants/union_room.h"', '''#include "constants/union_room.h"
#include "easy_chat.h"
#define PORTABLE 1
#include "platform/native_link.h"
#undef PORTABLE
extern u16 ExpansionLink_GetBlockReceivedSize(u8 who);
extern int ExpansionTrade_PairValid(const void *data, size_t size);''')
    donor = one(donor, '    u8 partnerConfirmStatus;\n    u8 filler_7C[2];', '''    u8 partnerConfirmStatus;
    bool8 nativeConfirmed;
    u8 nativeConfirmedPlayer;
    u8 nativeConfirmedPartner;
    u8 filler_7C[2];''')
    begin = vanilla.index('#ifdef PORTABLE\n// Read the completed cable block length')
    end = vanilla.index('#endif\n\nstatic bool8 BufferTradeParties', begin)
    helpers = vanilla[begin + len('#ifdef PORTABLE\n'):end]
    helpers = helpers.replace('GetBlockReceivedSize(', 'ExpansionLink_GetBlockReceivedSize(')
    a = helpers.index('// Validate a private copy:')
    b = helpers.index('static bool8 NativeTradeReject(void);', a)
    helpers = helpers[:a] + '''static bool8 NativeTradePartyBlockValid(u8 peer)
{
    if (!NativeTradeBlockSizeValid(peer, 200)) return FALSE;
    if (!ExpansionTrade_PairValid(gBlockRecvBuffer[peer], 200))
    {
        NativeLink_Abort(); gLinkErrorOccurred = TRUE; return FALSE;
    }
    return TRUE;
}
''' + helpers[b:]
    helpers = helpers.replace('GIFT_RIBBONS_COUNT', 'NUM_GIFT_RIBBONS')
    donor = one(donor, 'static bool8 BufferTradeParties(void)\n{', helpers + '\nstatic bool8 BufferTradeParties(void)\n{')
    for index in (0, 2, 4):
        old = f'            Trade_Memcpy(&gParties[B_TRAINER_OPPONENT_A][{index}], gBlockRecvBuffer[id ^ 1], '
        # Preserve donor spacing after the comma and match the full line.
        line = next((x for x in donor.splitlines() if x.startswith(old)), None)
        if line is None: raise ValueError('party receive anchor missing')
        donor = one(donor, line, '''            if (NativeLink_IsActive() && !NativeTradePartyBlockValid(id ^ 1)) return FALSE;
''' + line)
    for target, is_mail in (('gTradeMail', 'TRUE'), ('sTradeMenu->giftRibbons', 'FALSE')):
        prefix = '            Trade_Memcpy(' + target + ', gBlockRecvBuffer[id ^ 1],'
        line = next((x for x in donor.splitlines() if x.startswith(prefix)), None)
        if line is None: raise ValueError('auxiliary receive anchor missing')
        donor = one(donor, line, f'            if (NativeLink_IsActive() && !NativeTradeAuxBlockValid(id ^ 1, {is_mail})) return FALSE;\n' + line)
    # These functions are identical outside the existing world's PORTABLE
    # guards. Preserve donor-specific code elsewhere instead of replacing it.
    for signature in ('static void Leader_ReadLinkBuffer(u8 mpId, u8 status)',
                      'static void Follower_ReadLinkBuffer(u8 mpId, u8 status)',
                      'static void SetLinkData(u16 linkCmd, u16 cursorPosition)',
                      'static void CB_ProcessConfirmTradeInput(void)',
                      'static void SetSelectedMon(u8 cursorPosition)',
                      'static void HandleLinkDataReceive(void)'):
        old = extract_function(donor, signature)
        replacement = extract_function(vanilla, signature).replace('#ifdef PORTABLE', '#if defined(PLATFORM_NATIVE)')
        donor = one(donor, old, replacement)
    reject_start = vanilla.index('#ifdef PORTABLE\nstatic bool8 NativeTradeReject(void)\n{')
    reject_end = vanilla.index('#endif\n\nstatic void Leader_ReadLinkBuffer', reject_start)
    reject = vanilla[reject_start + len('#ifdef PORTABLE\n'):reject_end]
    donor = one(donor, 'static void Leader_ReadLinkBuffer(u8 mpId, u8 status)\n{', reject + '\nstatic void Leader_ReadLinkBuffer(u8 mpId, u8 status)\n{')
    donor = one(donor, 'static void TradeMons(u8 playerPartyIdx, u8 partnerPartyIdx)\n{\n    u8 friendship;', '''static void TradeMons(u8 playerPartyIdx, u8 partnerPartyIdx)
{
    u8 friendship;
    /* Experimental native trade is party-only and never trusts peer indices. */
    if (NativeLink_IsActive() && (playerPartyIdx >= PARTY_SIZE || partnerPartyIdx >= PARTY_SIZE
        || playerPartyIdx >= gPartiesCount[B_TRAINER_PLAYER]
        || partnerPartyIdx >= gPartiesCount[B_TRAINER_OPPONENT_A]))
    { NativeLink_Abort(); gLinkErrorOccurred = TRUE; return; }''')
    donor = one(donor, '    u16 partnerMail = GetMonData(partnerMon, MON_DATA_MAIL);', '''    u16 partnerMail = GetMonData(partnerMon, MON_DATA_MAIL);
    if (NativeLink_IsActive() && ((playerMail != MAIL_NONE && playerMail >= PARTY_SIZE)
        || (partnerMail != MAIL_NONE && partnerMail >= PARTY_SIZE)))
    { NativeLink_Abort(); gLinkErrorOccurred = TRUE; return; }''')
    donor = one(donor, 'static void CB2_FreeTradeAnim(void)\n{\n    if (!gPaletteFade.active)\n    {', '''static void CB2_FreeTradeAnim(void)
{
    if (!gPaletteFade.active)
    {
        if (NativeLink_IsActive()) SetVBlankCallback(NULL);''')
    # Do not proceed past a failed final sector write during a native trade.
    donor = one(donor, '            LinkFullSave_SetLastSectorSignature();', '''            if (NativeLink_IsActive()) {
                if (LinkFullSave_SetLastSectorSignature()) break;
            } else LinkFullSave_SetLastSectorSignature();''', expected=2)
    return donor

if __name__ == '__main__':
    if len(sys.argv) != 4: raise SystemExit('usage: patch_expansion_trade.py DONOR WORLD_TRADE OUTPUT')
    donor, vanilla, output = map(Path, sys.argv[1:])
    result = generate(donor.read_text(), vanilla.read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result)
