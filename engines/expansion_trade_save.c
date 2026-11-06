/* Require the donor's atomic save file store to finish before acknowledging a
 * native trade's final signature. Other donor save flows keep their behavior. */
#include "global.h"
#include "save.h"
#include "platform/frame.h"
#define PORTABLE 1
#include "platform/native_link.h"
#undef PORTABLE

bool8 __real_LinkFullSave_SetLastSectorSignature(void);
bool8 __wrap_LinkFullSave_SetLastSectorSignature(void)
{
    bool8 error = __real_LinkFullSave_SetLastSectorSignature();
    if (!NativeLink_IsActive()) return error;
    if (error || gDamagedSaveSectors) return TRUE;
    return frame_flush_save() != 0;
}
