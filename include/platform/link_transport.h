#ifndef GUARD_PLATFORM_LINK_TRANSPORT_H
#define GUARD_PLATFORM_LINK_TRANSPORT_H
#ifdef PORTABLE
#include <stdint.h>
struct LinkTransportInvitation
{
    uint64_t id;
    unsigned mode;
    char name[25];
};
/* NULL config disables IO. Network failures retry after 60 pumps but never
 * restore consent or activity. Protocol/auth failures stay closed until Init.
 * Pump only on the main thread, outside input callbacks. 1/0 success. */
int LinkTransport_Init(const char *configPath);
void LinkTransport_Pump(void);
void LinkTransport_Close(void);
int LinkTransport_Ready(void);
int LinkTransport_Offer(const char *target, unsigned mode);
int LinkTransport_Accept(uint64_t session);
int LinkTransport_Reject(uint64_t session);
/* Borrowed immutable storage, invalidated by the next pump/action/close. */
const struct LinkTransportInvitation *LinkTransport_PendingInvitation(void);
#endif
#endif
