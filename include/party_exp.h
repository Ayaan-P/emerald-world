#ifndef GUARD_PARTY_EXP_H
#define GUARD_PARTY_EXP_H

/* Base amounts before trainer, trade, and held-item multipliers. Each bench
 * member gets half independently. No participants means no participant award. */
static inline u16 PartyExp_BaseAward(u16 base, u8 participants, bool8 participated)
{
    u16 amount;
    if (participated && !participants)
        return 0;
    amount = participated ? base / participants : base / 2;
    return amount ? amount : 1;
}

static inline bool8 PartyExp_Eligible(u16 species, u16 hp, bool8 isEgg)
{
    return species != SPECIES_NONE && hp != 0 && !isEgg;
}

static inline u32 PartyExp_RecipientBase(u16 participantAmount, u16 shareAmount,
                                        bool8 enabled, bool8 heldShare, bool8 participated)
{
    u32 amount = participated ? participantAmount : 0;
    if (enabled ? !participated : heldShare)
        amount += shareAmount;
    return amount;
}

#endif
