#ifndef GUARD_PLATFORM_REPEAT_REPEL_H
#define GUARD_PLATFORM_REPEAT_REPEL_H
#ifdef PORTABLE
/* Script-facing entry points. Only the designated expiry script may use them. */
void RepeatRepel_Begin(void);
void RepeatRepel_DrawMenu(void);
void RepeatRepel_Commit(void);
void RepeatRepel_End(void);
#endif
#endif
