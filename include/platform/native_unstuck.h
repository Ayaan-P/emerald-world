#ifndef GUARD_PLATFORM_NATIVE_UNSTUCK_H
#define GUARD_PLATFORM_NATIVE_UNSTUCK_H
#if defined(PORTABLE) && !defined(_WIN32)
#include <stdbool.h>
#include <stdint.h>

enum NativeUnstuckResult {
    NATIVE_UNSTUCK_ALLOWED,
    NATIVE_UNSTUCK_COOLDOWN,
    NATIVE_UNSTUCK_STORAGE_ERROR,
    NATIVE_UNSTUCK_BAD_CLOCK,
};
/* Reserves a use before a warp. The sidecar is private to the selected save.
 * On a storage or clock failure the caller must not warp. No save bytes change. */
enum NativeUnstuckResult NativeUnstuck_Reserve(const char *savePath, uint64_t now,
                                                bool boxed, unsigned *remaining);
#endif
#endif
