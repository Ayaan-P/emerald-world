/* Test-only file relay: no sockets. Never link into a user binary. */
#define PORTABLE 1
#include "platform/native_link.h"
#include "platform/link_transport.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static FILE *incoming,*outgoing;
static struct LinkTransportInvitation invite;
static unsigned offered; static uint64_t accepting,session;
static int emit(void *ctx,const struct NativeLinkEvent *e)
{
    static const char hex[]="0123456789abcdef"; char words[33]; (void)ctx;
    for(unsigned i=0;i<16;i++){unsigned b=(e->command[i/2]>>(8*(i%2)))&255;words[2*i]=hex[b>>4];words[2*i+1]=hex[b&15];} words[32]=0;
    if(fprintf(outgoing,"L EVENT %u %" PRIu64 " %u %u %" PRIu32 " %" PRIu32 " %u %s\n",e->kind,e->session,e->mode,e->slot,e->generation,e->round,e->linkType,words)<0)return 0;
    return fflush(outgoing)==0;
}
int __wrap_LinkTransport_Init(const char *config)
{
    (void)config;const char *in=getenv("EW_FAKE_LINK_IN"),*out=getenv("EW_FAKE_LINK_OUT");
    if(!in||!out || !(incoming=fopen(in,"r")) || !(outgoing=fopen(out,"a"))) return 0;
    NativeLink_Init(emit,NULL);return 1;
}
int __wrap_LinkTransport_Ready(void){return incoming && outgoing;}
int __wrap_LinkTransport_OfferPending(void){return offered!=0;}
const struct LinkTransportInvitation *__wrap_LinkTransport_PendingInvitation(void){return invite.id ? &invite : NULL;}
int __wrap_LinkTransport_Offer(const char *target,unsigned mode){if(!__wrap_LinkTransport_Ready()||session||offered||invite.id)return 0;offered=mode;fprintf(outgoing,"L OFFER %u %s\n",mode,target);return fflush(outgoing)==0;}
int __wrap_LinkTransport_Accept(uint64_t id){if(id!=invite.id||session||accepting)return 0;accepting=id;fprintf(outgoing,"L ACCEPT %" PRIu64 "\n",id);return fflush(outgoing)==0;}
int __wrap_LinkTransport_Reject(uint64_t id){if(id!=invite.id)return 0;fprintf(outgoing,"L REJECT %" PRIu64 "\n",id);memset(&invite,0,sizeof invite);return fflush(outgoing)==0;}
static int decode(const char *s,uint16_t words[8])
{
    if(strlen(s)!=32)return 0;
    for(unsigned i=0;i<8;i++){unsigned a,b;if(sscanf(s+4*i,"%2x%2x",&a,&b)!=2)return 0;words[i]=(uint16_t)(a|(b<<8));}return 1;
}
void __wrap_LinkTransport_Pump(void)
{
    char line[512];if(!incoming)return;
    for(unsigned count=0;count<64;count++) {
        long offset=ftell(incoming);clearerr(incoming);
        if(!fgets(line,sizeof line,incoming)){clearerr(incoming);break;}
        size_t n=strlen(line);if(!n || line[n-1]!='\n'){fseek(incoming,offset,SEEK_SET);break;}
        unsigned mode,slot,kind,gen,round; uint64_t id;char name[25],a[33],b[33];
        if(sscanf(line,"L OFFER %" SCNu64 " %u %24s",&id,&mode,name)==3){invite.id=id;invite.mode=mode;strcpy(invite.name,name);}
        else if(sscanf(line,"L ADMIT %" SCNu64 " %u %u",&id,&mode,&slot)==3){
            if((accepting==id && invite.mode==mode)||offered==mode){session=id;offered=0;accepting=0;memset(&invite,0,sizeof invite);if(!NativeLink_Admit(id,mode,slot)) abort();}
            else abort();
        } else if(sscanf(line,"L COMMIT %u %" SCNu64 " %u %u %32s %32s",&kind,&id,&gen,&round,a,b)==6){
            uint16_t matrix[2][8];if(id!=session || !decode(a,matrix[0]) || !decode(b,matrix[1]) || NativeLink_Feed(kind,id,gen,round,matrix)<0)abort();
        } else if(sscanf(line,"L ABORT %" SCNu64,&id)==1){if(id==session){NativeLink_EndSession(id);session=0;}else if(id==invite.id)memset(&invite,0,sizeof invite);}
        else {fprintf(stderr,"fake link received invalid line: %s",line);abort();}
    }
    NativeLink_Pump();
}
