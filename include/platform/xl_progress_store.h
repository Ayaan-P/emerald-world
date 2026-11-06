#ifndef GUARD_PLATFORM_XL_PROGRESS_STORE_H
#define GUARD_PLATFORM_XL_PROGRESS_STORE_H
#include <stddef.h>
#include <stdbool.h>
/* The caller owns the bounded payload. Returns false on unavailable or invalid storage. */
bool XLProgressStore_Init(const char *savePath, bool enabled, void *payload, size_t size);
bool XLProgressStore_Save(const void *payload, size_t size);
void XLProgressStore_Close(void);
#endif
