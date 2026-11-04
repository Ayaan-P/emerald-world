#ifndef GUARD_PLATFORM_WORLD_ACTIVITY_H
#define GUARD_PLATFORM_WORLD_ACTIVITY_H
#ifdef PORTABLE
/* Main-thread, post-callback boundary only. Names are copied and validated.
 * Returns 1 when the interaction was consumed, 0 when unavailable.
 * Filter FIELD input only, never raw SDL/gMain keys needed by native menus.
 * Call Update once after each committed frame, including native activities. */
int WorldActivity_Interact(const char *peerName);
void WorldActivity_Update(void);
int WorldActivity_OwnsFieldInput(void);
unsigned short WorldActivity_FilterFieldKeys(unsigned short keys);
const char *WorldActivity_Status(void);
const char *WorldActivity_Phase(void);
unsigned WorldActivity_Mode(void);
/* Consume once after closing Talk. Bridge revalidates presence and facing. */
int WorldActivity_TakeTalkRequest(char peer[25]);
/* Portable cable-club helpers, not seat/map scripts. */
int WorldActivity_StartNativeBattle(unsigned mode);
void WorldActivity_ReturnToField(void);
/* Called at the real wild-encounter seam, before its transition takes the field. */
int WorldActivity_TryCoopWildBattle(void);
int WorldActivity_TryCoopTrainerBattle(void);
int WorldActivity_IsEncounterPending(void);
void WorldActivity_ReturnFromCoopWildBattle(void);
#endif
#endif
