#ifndef GUARD_PLATFORM_PLAYER_CONTROL_H
#define GUARD_PLATFORM_PLAYER_CONTROL_H
#ifdef PORTABLE
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
/* The endpoint must live beside the explicitly selected save in a private directory. */
bool PlayerControl_Init(const char *path, const char *savePath,
                        void (*state)(FILE *, uint32_t), bool (*shot)(FILE *));
void PlayerControl_Close(void);
void PlayerControl_BeforeFrame(void);
void PlayerControl_AfterFrame(uint32_t frame);
uint16_t PlayerControl_Buttons(void);
#endif
#endif
