#include "stub.h"
#include <assert.h>
u32 gDamagedSaveSectors; static int active, result, flush_result, flush_count;
int NativeLink_IsActive(void){return active;}
int frame_flush_save(void){flush_count++;return flush_result;}
bool8 __real_LinkFullSave_SetLastSectorSignature(void){return result;}
bool8 __wrap_LinkFullSave_SetLastSectorSignature(void);
int main(void){
 assert(!__wrap_LinkFullSave_SetLastSectorSignature() && !flush_count);
 active=1;flush_result=-1;assert(__wrap_LinkFullSave_SetLastSectorSignature() && flush_count==1);
 flush_result=0;assert(!__wrap_LinkFullSave_SetLastSectorSignature() && flush_count==2);
 gDamagedSaveSectors=1;assert(__wrap_LinkFullSave_SetLastSectorSignature() && flush_count==2);
 gDamagedSaveSectors=0;result=1;assert(__wrap_LinkFullSave_SetLastSectorSignature() && flush_count==2);
 return 0;
}
