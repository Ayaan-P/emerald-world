#ifndef GUARD_PLATFORM_BATTLE_RULES_WIRE_H
#define GUARD_PLATFORM_BATTLE_RULES_WIRE_H

/* Wire-only v1 marker. Never mutate the native engine's gLinkType. */
#define BATTLE_SPLIT_WIRE_BIT 0x8000
static inline u16 BattleRules_LinkType(u16 linkType, bool8 modernSplit)
{
    if ((linkType & 0xFF00) == 0x2200 && modernSplit)
        return linkType | BATTLE_SPLIT_WIRE_BIT;
    return linkType;
}

#endif
