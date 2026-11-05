#ifndef GUARD_PLATFORM_MEGA_WIRE_H
#define GUARD_PLATFORM_MEGA_WIRE_H
#ifdef PORTABLE
/* Transport uses an otherwise unused controller command. A full packet is
 * twelve bytes and native link appends four zero alignment bytes. */
#define MEGA_WIRE_MAGIC 0x4D
#define MEGA_WIRE_VERSION 1
#define MEGA_WIRE_ACTIVATE 1
#define MEGA_WIRE_REENTER 2
#define MEGA_WIRE_BYTES 12
#define MEGA_WIRE_PADDED_BYTES 16
static inline void MegaWire_Encode(u8 *p, u8 command, u8 form, u8 kind, u8 slot, u32 generation)
{
    p[0] = command; p[1] = 9; p[2] = 0;
    p[3] = MEGA_WIRE_MAGIC; p[4] = MEGA_WIRE_VERSION; p[5] = form; p[6] = kind;
    p[7] = slot; p[8] = generation; p[9] = generation >> 8; p[10] = generation >> 16; p[11] = generation >> 24;
}
static inline bool8 MegaWire_IsCandidate(const u8 *p, u16 size, u8 command)
{
    return size >= 4 && p[0] == command && p[3] == MEGA_WIRE_MAGIC;
}
static inline bool8 MegaWire_Valid(const u8 *p, u16 size, u8 command, u8 formCount, u32 generation)
{
    u32 packetGeneration;
    if (size != MEGA_WIRE_PADDED_BYTES || p[0] != command || p[1] != 9 || p[2]
     || p[3] != MEGA_WIRE_MAGIC || p[4] != MEGA_WIRE_VERSION
     || !p[5] || p[5] >= formCount || (p[6] != MEGA_WIRE_ACTIVATE && p[6] != MEGA_WIRE_REENTER)
     || p[7] >= 6 || p[12] || p[13] || p[14] || p[15]) return FALSE;
    packetGeneration = (u32)p[8] | ((u32)p[9] << 8) | ((u32)p[10] << 16) | ((u32)p[11] << 24);
    return generation && packetGeneration == generation;
}
#endif
#endif
