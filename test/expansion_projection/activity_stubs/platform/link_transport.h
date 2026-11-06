#include "stub.h"
struct LinkTransportInvitation { u64 id; unsigned mode; char name[25]; };
int LinkTransport_Ready(void); int LinkTransport_Reject(u64); int LinkTransport_Accept(u64); int LinkTransport_Offer(const char *,unsigned); int LinkTransport_OfferPending(void); const struct LinkTransportInvitation *LinkTransport_PendingInvitation(void);
