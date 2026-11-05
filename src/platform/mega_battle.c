#ifdef PORTABLE
#include "global.h"
#include "constants/pokemon.h"
#include "platform/mega_battle.h"
#include <string.h>

void MegaBattle_Reset(struct MegaBattleState *state)
{
    if (state) memset(state, 0, sizeof(*state));
}

u8 MegaBattle_GetForm(const struct MegaBattleState *state, u8 owner, u8 slot)
{
    if (!state || owner >= MEGA_TRAINERS || slot >= MEGA_PARTY_SLOTS)
        return MEGA_FORM_NONE;
    return state->forms[owner][slot];
}

bool8 MegaForm_Calculate(u8 form, const struct MegaStatInput *input,
                         MegaNatureAdjust nature, struct MegaBattleStats *result)
{
    const struct MegaFormData *data = MegaForm_Get(form);
    struct MegaBattleStats computed = {0};
    u8 base[MEGA_STAT_COUNT];
    u16 values[MEGA_STAT_COUNT];
    u8 i;
    if (!data || !input || !nature || !result || input->level < 1 || input->level > 100 || input->nature >= 25)
        return FALSE;
    for (i = 0; i < MEGA_STAT_COUNT; i++)
        if (input->iv[i] > 31) return FALSE;
    base[0] = data->attack; base[1] = data->defense; base[2] = data->speed;
    base[3] = data->spAttack; base[4] = data->spDefense;
    for (i = 0; i < MEGA_STAT_COUNT; i++)
    {
        u16 stat = ((2 * base[i] + input->iv[i] + input->ev[i] / 4) * input->level) / 100 + 5;
        values[i] = nature(input->nature, stat, STAT_ATK + i);
    }
    computed.attack = values[0]; computed.defense = values[1]; computed.speed = values[2];
    computed.spAttack = values[3]; computed.spDefense = values[4];
    computed.type1 = data->type1; computed.type2 = data->type2; computed.ability = data->ability;
    *result = computed;
    return TRUE;
}

/* Calculate before consuming the trainer's once-per-battle choice. Call only
 * after revalidating the live held item and the trainer-local party slot. */
u8 MegaBattle_Transform(struct MegaBattleState *state, u8 owner, u8 slot,
                        u16 species, u8 stone, bool8 hasKey, bool8 conscious,
                        const struct MegaStatInput *input, MegaNatureAdjust nature,
                        struct MegaBattleStats *result)
{
    struct MegaBattleStats computed;
    u8 form;
    if (!state || !result || owner >= MEGA_TRAINERS || slot >= MEGA_PARTY_SLOTS
     || !hasKey || !conscious || state->used[owner] || state->forms[owner][slot])
        return MEGA_FORM_NONE;
    form = MegaForm_Find(species, stone);
    if (!form || !MegaForm_Calculate(form, input, nature, &computed))
        return MEGA_FORM_NONE;
    state->forms[owner][slot] = form;
    state->used[owner] = TRUE;
    *result = computed;
    return form;
}
#endif
