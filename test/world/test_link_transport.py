"""Native transport tests: real AF_UNIX peer, only the engine adapter is stubbed."""
import ctypes as C
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
STUB = r'''
#include "platform/native_link.h"
#include <sys/socket.h>
#include <errno.h>
int blockSend, chunkSend;
ssize_t __real_send(int fd,const void *p,size_t n,int flags);
ssize_t __wrap_send(int fd,const void *p,size_t n,int flags) {
if(blockSend) { errno=EAGAIN;return -1; }
if(chunkSend && n>7)n=7;
return __real_send(fd,p,n,flags);
}
static NativeLinkEmit cb; static void *ctx;
unsigned admits, feeds, aborts; uint64_t lastSid; unsigned lastMode,lastSlot;
uint16_t matrixSeen[2][8];
void NativeLink_Init(NativeLinkEmit e, void *c) { cb=e;ctx=c; }
void NativeLink_Abort(void) { aborts++; }
void NativeLink_EndSession(uint64_t s) { (void)s; aborts++; }
int NativeLink_Admit(uint64_t s,unsigned m,unsigned p) { admits++;lastSid=s;lastMode=m;lastSlot=p;return 1; }
int NativeLink_Feed(unsigned k,uint64_t s,uint32_t g,uint32_t r,const uint16_t m[2][8]) {
unsigned i,j; (void)k;(void)g;(void)r;feeds++;lastSid=s;
for(i=0;i<2;i++) { for(j=0;j<8;j++)matrixSeen[i][j]=m[i][j]; } return 1; }
void NativeLink_Pump(void) {}
int emit(unsigned r) { struct NativeLinkEvent e={0};e.kind=4;e.mode=1;e.slot=0;e.session=18446744073709551615ULL;e.generation=2;e.round=r;e.linkType=4660;e.command[0]=0x1234;return cb?cb(ctx,&e):0; }
'''

class TransportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        p = Path(cls.build.name)
        (p/'stub.c').write_text(STUB)
        subprocess.run(['cc','-shared','-fPIC','-std=c99','-Wall','-Wextra','-Werror','-DPORTABLE','-I'+str(ROOT/'include'),str(ROOT/'src/platform/link_transport.c'),str(p/'stub.c'),'-Wl,--wrap=send','-o',str(p/'transport.so')],check=True)
        cls.lib=C.CDLL(str(p/'transport.so'))
        cls.lib.LinkTransport_Init.argtypes=[C.c_char_p]
        cls.lib.LinkTransport_Accept.argtypes=[C.c_uint64]
        cls.lib.LinkTransport_Reject.argtypes=[C.c_uint64]
        cls.lib.LinkTransport_Offer.argtypes=[C.c_char_p,C.c_uint]
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
        self.server=socket.socket(socket.AF_UNIX);self.server.bind(str(self.path/'sock'));self.server.listen();self.server.settimeout(1)
        self.config=self.path/'config';self.config.write_text(f'socket {self.path}/sock\ntrainer Alice\ntoken '+ 'a'*64+'\ntelemetry /tmp/ignored\n')
        self.peer=None
    def tearDown(self):
        self.lib.LinkTransport_Close()
        if self.peer:self.peer.close()
        self.server.close();self.tmp.cleanup()
    def pump(self):
        for _ in range(5): self.lib.LinkTransport_Pump();time.sleep(.001)
    def connect(self, welcome=True):
        self.assertEqual(self.lib.LinkTransport_Init(str(self.config).encode()),1)
        self.pump();self.peer,_=self.server.accept();self.peer.settimeout(1)
        self.assertEqual(self.peer.recv(4096),b'HELLO 1 Alice '+b'a'*64+b' LINK\n')
        if welcome:
            self.peer.sendall(b'WELCOME 1 Alice 1 LINK\n');self.pump()
    def test_disabled_and_real_handshake(self):
        self.assertEqual(self.lib.LinkTransport_Init(None),1)
        self.pump();self.assertEqual(self.lib.LinkTransport_Offer(b'Bob',1),0)
        self.connect()
        self.assertEqual(self.lib.LinkTransport_Offer(b'Bob',1),1)
        self.pump();self.assertEqual(self.peer.recv(4096),b'L OFFER 1 Bob\n')

    def stat(self, name): return C.c_uint.in_dll(self.lib,name).value
    def incoming(self, wire):
        self.peer.sendall(wire);self.pump()
    def admit(self):
        self.connect()
        self.incoming(b'L OFFER 18446744073709551615 1 Bob\n')
        self.assertEqual(self.lib.LinkTransport_Accept(2**64-1),1)
        self.pump();self.assertEqual(self.peer.recv(4096),b'L ACCEPT 18446744073709551615\n')
        self.incoming(b'L ADMIT 18446744073709551615 1 0\n')
    def test_commit_and_event_little_endian(self):
        self.admit();before=self.stat('feeds')
        self.incoming(b'L COMMIT 3 18446744073709551615 2 1 34120000000000000000000000000000 78560000000000000000000000000000\n')
        self.assertEqual(self.stat('feeds'),before+1)
        matrix=(C.c_uint16*16).in_dll(self.lib,'matrixSeen')
        self.assertEqual((matrix[0],matrix[8]),(0x1234,0x5678))
        self.assertEqual(self.lib.emit(7),1);self.pump()
        self.assertEqual(self.peer.recv(4096),b'L EVENT 4 18446744073709551615 1 0 2 7 4660 34120000000000000000000000000000\n')
    def test_overflow_and_conflict_fail_closed(self):
        for wire in [b'L OFFER 18446744073709551616 1 Bob\n',b'L OFFER 1 4 Bob\n',b'L OFFER 1 1 Bob extra\n',b'L OFFER 1 1 B!b\n',b'x'*513]:
            self.connect();self.incoming(wire)
            self.assertEqual(self.lib.LinkTransport_Ready(),0)
            self.peer.close();self.peer=None;self.lib.LinkTransport_Close()
    def test_partial_read_and_duplicate_admit(self):
        self.admit();before=self.stat('admits')
        self.peer.sendall(b'L ADMIT 18446744073709551615 1');self.pump()
        self.assertEqual(self.lib.LinkTransport_Ready(),1)
        self.incoming(b' 0\n');self.assertEqual(self.stat('admits'),before)
        self.incoming(b'L ADMIT 18446744073709551615 1 1\n')
        self.assertEqual(self.lib.LinkTransport_Ready(),0)
    def test_fifo_backpressure_partial_writes(self):
        self.admit();blocked=C.c_int.in_dll(self.lib,'blockSend');chunk=C.c_int.in_dll(self.lib,'chunkSend')
        blocked.value=1;accepted=0
        try:
            while self.lib.emit(accepted):
                accepted+=1
                self.assertLess(accepted,2000)
            self.pump();self.assertEqual(self.lib.emit(accepted),0)
            blocked.value=0;chunk.value=1
            result=b'';self.peer.setblocking(False)
            for _ in range(10000):
                self.lib.LinkTransport_Pump()
                try:result+=self.peer.recv(65536)
                except BlockingIOError:pass
                if result.count(b'\n')==accepted:break
            lines=result.splitlines()
            self.assertEqual(len(lines),accepted)
            self.assertLessEqual(len(result),65536)
            self.assertEqual([int(line.split()[7]) for line in lines],list(range(accepted)))
            self.assertEqual(self.lib.emit(accepted),1)
        finally:blocked.value=0;chunk.value=0
    def test_config_full_validation(self):
        original=self.config.read_bytes()
        for suffix in [b'trainer Bob\n',b'unknown key\n',b'#nul\x00hidden\n',b'#bad\xff\n',b'telemetry '+b'x'*1024+b'\n']:
            self.config.write_bytes(original+suffix)
            self.assertEqual(self.lib.LinkTransport_Init(str(self.config).encode()),0)
        self.config.write_bytes(original.replace(b'trainer Alice',b'trainer '+b'A'*25))
        self.assertEqual(self.lib.LinkTransport_Init(str(self.config).encode()),0)
    def test_windows_branch_compile_only(self):
        p=Path(self.build.name)/'win';p.mkdir(exist_ok=True)
        (p/'windows.h').write_text('''#ifndef TEST_WINDOWS_H
#define TEST_WINDOWS_H
#include <stddef.h>
#include <stdio.h>
#define CP_UTF8 65001
#define MB_ERR_INVALID_CHARS 8
#define MOVEFILE_REPLACE_EXISTING 1
int MultiByteToWideChar(unsigned,unsigned,const char *,int,wchar_t *,int);
FILE *_wfopen(const wchar_t *,const wchar_t *);
int MoveFileExW(const wchar_t *,const wchar_t *,unsigned);
#endif
''')
        (p/'winsock2.h').write_text('''#include <stddef.h>
#include <stdint.h>
typedef uintptr_t SOCKET;
typedef unsigned long u_long;
typedef struct { unsigned short wVersion; } WSADATA;
struct in_addr { unsigned long s_addr; };
struct sockaddr { unsigned short family; };
struct sockaddr_in { short sin_family; unsigned short sin_port; struct in_addr sin_addr; };
typedef struct { int unused; } fd_set;
struct timeval { long tv_sec,tv_usec; };
#define INVALID_SOCKET ((SOCKET)-1)
#define MAKEWORD(a,b) ((a)|((b)<<8))
#define AF_INET 2
#define SOCK_STREAM 1
#define IPPROTO_TCP 6
#define INADDR_LOOPBACK 0x7f000001
#define FIONBIO 1
#define WSAEWOULDBLOCK 10035
#define WSAEINTR 10004
#define WSAEINPROGRESS 10036
#define SOL_SOCKET 65535
#define SO_ERROR 4103
#define FD_ZERO(p) ((void)(p))
#define FD_SET(fd,p) ((void)(fd),(void)(p))
int WSAStartup(int,WSADATA *); int WSACleanup(void); int WSAGetLastError(void);
int closesocket(SOCKET); SOCKET socket(int,int,int);
int ioctlsocket(SOCKET,long,u_long *);
unsigned long htonl(unsigned long); unsigned short htons(unsigned short);
int connect(SOCKET,const struct sockaddr *,int);
int send(SOCKET,const char *,int,int); int recv(SOCKET,char *,int,int);
int select(int,fd_set *,fd_set *,fd_set *,const struct timeval *);
int getsockopt(SOCKET,int,int,char *,int *);
''')
        subprocess.run(['cc','-fsyntax-only','-std=c99','-Wall','-Wextra','-Werror','-DPORTABLE','-D_WIN32','-I'+str(p),'-I'+str(ROOT/'include'),str(ROOT/'src/platform/link_transport.c')],check=True)
        subprocess.run(['cc','-fsyntax-only','-std=c99','-Wall','-Wextra','-Werror',str(ROOT/'src/platform/link_transport.c')],check=True)
    def test_pending_reject_and_matching_abort(self):
        class Invitation(C.Structure):
            _fields_=[('id',C.c_uint64),('mode',C.c_uint),('name',C.c_char*25)]
        self.lib.LinkTransport_PendingInvitation.restype=C.POINTER(Invitation)
        self.connect();self.incoming(b'L OFFER 5 3 Bob\n')
        invitation=self.lib.LinkTransport_PendingInvitation().contents
        self.assertEqual((invitation.id,invitation.mode,invitation.name),(5,3,b'Bob'))
        self.assertEqual(self.lib.LinkTransport_Reject(5),1);self.pump()
        self.assertEqual(self.peer.recv(4096),b'L REJECT 5\n')
        self.assertFalse(self.lib.LinkTransport_PendingInvitation())
        self.incoming(b'L OFFER 6 1 Bob\n');self.lib.LinkTransport_Accept(6);self.pump();self.peer.recv(4096)
        self.incoming(b'L ADMIT 6 1 0\n');before=self.stat('aborts')
        self.incoming(b'L ABORT 7\n');self.assertEqual(self.stat('aborts'),before)
        self.incoming(b'L ABORT 6\n');self.assertEqual(self.stat('aborts'),before+1)
    def test_disconnect_reconnect_does_not_replay_activity(self):
        self.admit();blocked=C.c_int.in_dll(self.lib,'blockSend')
        blocked.value=1
        self.assertEqual(self.lib.emit(9),1)
        self.peer.shutdown(socket.SHUT_RDWR);self.peer.close();self.peer=None
        before=self.stat('aborts')
        try:self.pump()
        finally:blocked.value=0
        self.assertGreater(self.stat('aborts'),before)
        for _ in range(180):self.lib.LinkTransport_Pump()
        self.peer,_=self.server.accept();self.peer.settimeout(1);self.pump()
        self.assertEqual(self.peer.recv(65536),b'HELLO 1 Alice '+b'a'*64+b' LINK\n')
        self.incoming(b'WELCOME 1 Alice 2 LINK\n')
        self.assertEqual(self.lib.emit(10),0)
        self.assertEqual(self.lib.LinkTransport_Accept(2**64-1),0)
    def test_fixed_error_releases_pending_intent(self):
        self.connect();self.assertEqual(self.lib.LinkTransport_Offer(b'Bob',1),1);self.pump();self.peer.recv(4096)
        self.incoming(b'L ERROR not_adjacent\n')
        self.assertEqual(self.lib.LinkTransport_Offer(b'Bob',1),1)
        self.incoming(b'L ERROR arbitrary_text\n');self.assertEqual(self.lib.LinkTransport_Ready(),0)
    def test_presence_race_retries_without_activity(self):
        self.connect(welcome=False);self.incoming(b'ERROR PRESENCE\n')
        for _ in range(180):self.lib.LinkTransport_Pump()
        retry,_=self.server.accept();retry.settimeout(1)
        try:
            self.pump();self.assertEqual(retry.recv(4096),b'HELLO 1 Alice '+b'a'*64+b' LINK\n')
            retry.sendall(b'WELCOME 1 Alice 2 LINK\n');self.pump()
            self.assertEqual(self.lib.LinkTransport_Ready(),1)
        finally:retry.close()

if __name__=='__main__':unittest.main()
