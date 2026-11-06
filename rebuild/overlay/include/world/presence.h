#ifndef EW_PRESENCE_H
#define EW_PRESENCE_H
/* Main-thread only. With no EW_WORLD_CONFIG this is a no-op. */
void EwPresenceTick(void);
void EwPresenceShutdown(void);
#endif
