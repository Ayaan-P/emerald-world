#define main component_main
#include "COMPONENT_SOURCE"
#undef main
int main(void)
{
 unsigned seed=7,i,j;char row[510],hex[193];
 component_main();level=4;fail_alloc=0;b1.location.mapGroup=29;b1.location.mapNum=7;b2.playerTrainerId[0]=42;
 for(i=0;i<6000;i++){
  WorldTrickQuiz_Enter();
  /* Exercise bounded native decoding with invalid lengths, bytes and indices. */
  for(j=0;j<sizeof(hex)-1;j++){seed=seed*1664525U+1013904223U;hex[j]="0123456789abcdefxyz"[(seed>>16)%19];}hex[192]=0;
  snprintf(row,sizeof(row),"TQ BEGIN %u 1 5061636b",sQuiz.nonce);line(row);
  snprintf(row,sizeof(row),"TQ ROW %u 1 %u %u %s 4f6e65 54776f 5468726565",sQuiz.nonce,i%8,i%5,hex);line(row);
  snprintf(row,sizeof(row),"TQ END %u 1",sQuiz.nonce);line(row);
  WorldTrickQuiz_Prepare();assert(gSpecialVar_Result==0&&!sQuiz.ready);
 }
 /* Partial rows, duplicate indices and wrong final revision cannot become usable. */
 WorldTrickQuiz_Enter();snprintf(row,sizeof(row),"TQ BEGIN %u 1 5061636b",sQuiz.nonce);line(row);
 for(i=0;i<5;i++){snprintf(row,sizeof(row),"TQ ROW %u 1 0 1 57686963683f 4f6e65 54776f 5468726565",sQuiz.nonce);line(row);}
 snprintf(row,sizeof(row),"TQ END %u 1",sQuiz.nonce);line(row);assert(!sQuiz.ready);
 WorldTrickQuiz_Enter();pack(sQuiz.nonce);WorldTrickQuiz_Prepare();WorldTrickQuiz_Accept();
 {unsigned revision=sQuiz.revision;snprintf(row,sizeof(row),"TQ BEGIN %u 4294967295 4576696c",sQuiz.nonce);line(row);assert(sQuiz.revision==revision);}
 WorldTrickQuiz_Choices();b1.location.mapNum=0;gSpecialVar_Result=1;WorldTrickQuiz_Grade();assert(gSpecialVar_Result==0);
 return 0;
}
