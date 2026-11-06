/* Require the donor's atomic save file store to finish before acknowledging a
 * link trade's final signature, including when a session disconnects. */
#include "global.h"
#include "save.h"
#include "platform/frame.h"

bool8 __real_LinkFullSave_SetLastSectorSignature(void);
bool8 __wrap_LinkFullSave_SetLastSectorSignature(void)
{
    bool8 error = __real_LinkFullSave_SetLastSectorSignature();
    if (error || gDamagedSaveSectors) return TRUE;
    return frame_flush_save() != 0;
}
