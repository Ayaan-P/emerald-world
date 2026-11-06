/* Supplemental native Dex metadata. The GBA save layout remains unchanged. */
#ifdef PORTABLE
#include "global.h"
#include "pokedex.h"
#include "platform/expanded_species.h"
#include "platform/native_save.h"
#include <stdio.h>
#include <string.h>
#ifndef _WIN32
#include <sys/stat.h>
#endif

/* Wire ABI, explicitly little endian. EDX1's two 24-byte slots remain intact
 * at offset zero. EDX2 appends two slots: magic, trainer ID, sequence, schema
 * (2), National maximum (1025), seen[129], caught[129], CRC32. Bit n-1 means
 * National n, never engine species n. Padding bits must be zero.
 * The pinned bb3fd057 donor ends at Pecharunt (1025). Range/schema changes
 * require a new explicit decoder, not a changed meaning for existing bytes.
 * Old executables cannot see EDX2 progress. Do not use old writers after
 * migration: the preserved EDX1 prefix is an import snapshot, not a mirror. */
#define LEGACY_SIZE 24
#define LEGACY_PREFIX (2 * LEGACY_SIZE)
#define DEX_BYTES ((EXPANDED_DEX_NATIONAL_MAX + 7) / 8)
#define RECORD_SIZE (20 + 2 * DEX_BYTES + 4)
#define JOURNAL_SIZE (LEGACY_PREFIX + 2 * RECORD_SIZE)
static u8 sJournal[JOURNAL_SIZE];
static u8 sRecord[RECORD_SIZE];
static u8 sTrainer[4];
static u8 sSeen[DEX_BYTES], sCaught[DEX_BYTES], sSlot;
static bool8 sBound;
#ifndef _WIN32
static FILE *sFile;
#endif

static u32 Read32(const u8 *p)
{
    return (u32)p[0] | (u32)p[1] << 8 | (u32)p[2] << 16 | (u32)p[3] << 24;
}

static void Write32(u8 *p, u32 value)
{
    u32 i;
    for (i = 0; i < 4; ++i)
        p[i] = value >> (8 * i);
}

static u32 Checksum(const u8 *bytes, u32 size)
{
    u32 crc = 0xFFFFFFFF;
    u32 i, bit;
    for (i = 0; i < size; ++i)
    {
        crc ^= bytes[i];
        for (bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1)));
    }
    return ~crc;
}

static bool8 Valid(const u8 *bytes)
{
    return memcmp(bytes, "EDX2", 4) == 0 && Read32(bytes + 12) == 2
        && Read32(bytes + 16) == EXPANDED_DEX_NATIONAL_MAX
        && (bytes[20 + DEX_BYTES - 1] & ~1) == 0
        && (bytes[20 + 2 * DEX_BYTES - 1] & ~1) == 0
        && Read32(bytes + RECORD_SIZE - 4) == Checksum(bytes, RECORD_SIZE - 4);
}

#ifndef _WIN32
static bool8 ValidLegacy(const u8 *bytes)
{
    return memcmp(bytes, "EDX1", 4) == 0 && Read32(bytes + 12) == 1
        && (bytes[16] & ~7) == 0 && (bytes[17] & ~7) == 0
        && bytes[18] == 0 && bytes[19] == 0
        && Read32(bytes + 20) == Checksum(bytes, 20);
}

static void ImportLegacy(const u8 *bytes)
{
    /* EDX1 schema 1 was exactly this ordered roster. Keep this frozen even
     * when generated species IDs or the playable selection grow. */
    static const u16 national[] = {790, 808, 999};
    u32 i;
    memcpy(sRecord, "EDX2", 4);
    memcpy(sRecord + 4, bytes + 4, 8);
    Write32(sRecord + 12, 2);
    Write32(sRecord + 16, EXPANDED_DEX_NATIONAL_MAX);
    for (i = 0; i < ARRAY_COUNT(national); ++i)
    {
        u32 index = national[i] - 1;
        if (bytes[16] & (1 << i))
            sRecord[20 + index / 8] |= 1 << (index % 8);
        if (bytes[17] & (1 << i))
            sRecord[20 + DEX_BYTES + index / 8] |= 1 << (index % 8);
    }
    Write32(sRecord + RECORD_SIZE - 4, Checksum(sRecord, RECORD_SIZE - 4));
}
#endif

void ExpandedDex_Reset(void)
{
    /* Soft reset only drops trainer binding. Init owns the file lifetime. */
    sBound = FALSE;
    memset(sSeen, 0, sizeof(sSeen));
    memset(sCaught, 0, sizeof(sCaught));
    memset(sTrainer, 0, sizeof(sTrainer));
}

void ExpandedDex_Init(const char *savePath, bool8 allowPersistence)
{
#ifndef _WIN32
    char path[4096];
    struct stat info;
    bool8 valid[2] = {FALSE, FALSE};
    u32 i;
    if (sFile != NULL)
        fclose(sFile);
    sFile = NULL;
#endif
    ExpandedDex_Reset();
    memset(sRecord, 0, sizeof(sRecord));
    memset(sJournal, 0, sizeof(sJournal));
    sSlot = 0;
#ifndef _WIN32
    if (!allowPersistence || savePath == NULL)
        return;
    if (snprintf(path, sizeof(path), "%s.expanded-dex", savePath) >= (int)sizeof(path))
        return;
    sFile = NativeSave_Open(path);
    if (sFile == NULL)
        goto unavailable;
    if (fstat(fileno(sFile), &info) != 0 || (info.st_mode & 077) != 0
        || info.st_size > JOURNAL_SIZE)
        goto close_unavailable;
    /* Preserve legacy bytes. Slots are read independently for torn writes. */
    NativeSave_Read(sFile, 0, sJournal, LEGACY_PREFIX);
    for (i = 0; i < 2; ++i)
    {
        u8 *slot = sJournal + LEGACY_PREFIX + i * RECORD_SIZE;
        valid[i] = NativeSave_Read(sFile, LEGACY_PREFIX + i * RECORD_SIZE, slot, RECORD_SIZE)
            && Valid(slot);
        /* Recognize an intact unknown version/schema without mistaking a
         * torn known header for a future format and disabling CRC recovery. */
        if (memcmp(slot, "EDX", 3) == 0 && (!valid[i])
            && Read32(slot + RECORD_SIZE - 4) == Checksum(slot, RECORD_SIZE - 4)
            && (memcmp(slot, "EDX2", 4) != 0 || Read32(slot + 12) != 2
                || Read32(slot + 16) != EXPANDED_DEX_NATIONAL_MAX))
            goto close_unavailable;
    }
    if (valid[0] || valid[1])
    {
        sSlot = valid[1] && (!valid[0]
            || (s32)(Read32(sJournal + LEGACY_PREFIX + RECORD_SIZE + 8)
                   - Read32(sJournal + LEGACY_PREFIX + 8)) > 0);
        memcpy(sRecord, sJournal + LEGACY_PREFIX + sSlot * RECORD_SIZE, RECORD_SIZE);
    }
    else if (info.st_size <= LEGACY_PREFIX)
    {
        /* Explicit EDX1 import. Never resurrect this snapshot after EDX2
         * writes: if both new slots are damaged, fail closed instead. */
        /* Select newest BEFORE trainer binding, never
         * search backwards for a different trainer's matching snapshot. */
        valid[0] = ValidLegacy(sJournal);
        valid[1] = ValidLegacy(sJournal + LEGACY_SIZE);
        if (valid[0] || valid[1])
        {
            i = valid[1] && (!valid[0]
                || (s32)(Read32(sJournal + LEGACY_SIZE + 8) - Read32(sJournal + 8)) > 0);
            ImportLegacy(sJournal + i * LEGACY_SIZE);
            /* The first mutation writes both the imported baseline and its
             * successor, so corrupting the new slot still recovers EDX1 data. */
            memcpy(sJournal + LEGACY_PREFIX, sRecord, RECORD_SIZE);
        }
    }
    return;
close_unavailable:
    fclose(sFile);
    sFile = NULL;
unavailable:
    fprintf(stderr, "Expanded Dex is session-only: private sidecar unavailable.\n");
#else
    (void)savePath;
    (void)allowPersistence;
#endif
}

static void BindTrainer(void)
{
    if (sBound && memcmp(sTrainer, gSaveBlock2Ptr->playerTrainerId, 4) == 0)
        return;
    memcpy(sTrainer, gSaveBlock2Ptr->playerTrainerId, 4);
    sBound = TRUE;
    memset(sSeen, 0, sizeof(sSeen));
    memset(sCaught, 0, sizeof(sCaught));
    if (Valid(sRecord) && memcmp(sTrainer, sRecord + 4, 4) == 0)
    {
        memcpy(sSeen, sRecord + 20, DEX_BYTES);
        memcpy(sCaught, sRecord + 20 + DEX_BYTES, DEX_BYTES);
    }
}

static void Persist(void)
{
    u32 sequence = Read32(sRecord + 8) + 1;
    memset(sRecord, 0, sizeof(sRecord));
    memcpy(sRecord, "EDX2", 4);
    memcpy(sRecord + 4, sTrainer, 4);
    Write32(sRecord + 8, sequence);
    Write32(sRecord + 12, 2);
    Write32(sRecord + 16, EXPANDED_DEX_NATIONAL_MAX);
    memcpy(sRecord + 20, sSeen, DEX_BYTES);
    memcpy(sRecord + 20 + DEX_BYTES, sCaught, DEX_BYTES);
    Write32(sRecord + RECORD_SIZE - 4, Checksum(sRecord, RECORD_SIZE - 4));
    sSlot ^= 1;
    memcpy(sJournal + LEGACY_PREFIX + sSlot * RECORD_SIZE, sRecord, RECORD_SIZE);
#ifndef _WIN32
    if (sFile != NULL)
    {
        struct stat info;
        /* NativeSave keeps the inode lock, checks owner/links, flushes/fsyncs.
         * Unchanged previous-slot bytes provide CRC recovery after torn writes. */
        if (fstat(fileno(sFile), &info) != 0 || (info.st_mode & 077) != 0
            || !NativeSave_Write(sFile, sJournal, sizeof(sJournal)))
        {
            fclose(sFile);
            sFile = NULL;
            fprintf(stderr, "Expanded Dex could not be persisted. Trainer save is unchanged.\n");
        }
    }
#endif
}

s8 ExpandedDex_GetSetFlag(u16 nationalDexNo, u8 caseID)
{
    u16 species, index;
    u8 mask;
    if (nationalDexNo == 0 || nationalDexNo > EXPANDED_DEX_NATIONAL_MAX)
        return FALSE;
    species = ExpandedSpecies_FromNationalDexNumber(nationalDexNo);
    if (!ExpandedSpecies_IsPlayable(species)
        || ExpandedSpecies_NationalDexNumber(species) != nationalDexNo
        || gSaveBlock2Ptr == NULL)
        return FALSE;
    index = (nationalDexNo - 1) / 8;
    mask = 1 << ((nationalDexNo - 1) % 8);
    BindTrainer();
    switch (caseID)
    {
    case FLAG_GET_SEEN: return (sSeen[index] & mask) != 0;
    case FLAG_GET_CAUGHT: return (sCaught[index] & mask) != 0;
    case FLAG_SET_SEEN:
        if (!(sSeen[index] & mask))
        {
            sSeen[index] |= mask;
            Persist();
        }
        break;
    case FLAG_SET_CAUGHT:
        if (!(sCaught[index] & mask))
        {
            sCaught[index] |= mask;
            Persist();
        }
        break;
    }
    return FALSE; /* Match the native setter return convention. */
}
#endif
