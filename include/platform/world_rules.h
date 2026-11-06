#ifndef GUARD_PLATFORM_WORLD_RULES_H
#define GUARD_PLATFORM_WORLD_RULES_H
#ifdef PORTABLE
#include "gba/types.h"
#define WORLD_RULE_PARTY_EXP 1u
#define WORLD_RULE_REUSABLE_TMS 2u
#define WORLD_RULE_MODERN_SPLIT 4u
#define WORLD_RULE_MEGA_EVOLUTION 8u
#define WORLD_RULE_EXPANDED_ROSTER 16u
/* Startup-only policy. No save flag or live menu can mutate it. */
bool8 WorldRules_Init(const char *descriptor);
bool8 WorldRules_Enabled(u32 rule);
u32 WorldRules_Mask(void);
const char *WorldRules_Wire(void);
#endif
#endif
