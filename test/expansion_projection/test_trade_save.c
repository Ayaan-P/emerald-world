#include "stub.h"
#include <assert.h>
u32 gDamagedSaveSectors; static int result, flush_result, flush_count;
int frame_flush_save(void){flush_count++;return flush_result;}
bool8 __real_LinkFullSave_SetLastSectorSignature(void){return result;}
bool8 __wrap_LinkFullSave_SetLastSectorSignature(void);
int main(void){
 assert(!__wrap_LinkFullSave_SetLastSectorSignature() && flush_count==1);
 flush_result=-1;assert(__wrap_LinkFullSave_SetLastSectorSignature() && flush_count==2);
 flush_result=0;assert(!__wrap_LinkFullSave_SetLastSectorSignature() && flush_count==3);
 gDamagedSaveSectors=1;assert(__wrap_LinkFullSave_SetLastSectorSignature() && flush_count==3);
 gDamagedSaveSectors=0;result=1;assert(__wrap_LinkFullSave_SetLastSectorSignature() && flush_count==3);
 return 0;
}
