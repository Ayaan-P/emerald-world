"""Add exchange diagnostics only to the disposable donor test checkout."""
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/platform/world_coop.c'
s=p.read_text().replace('#ifdef PORTABLE\n#include "global.h"','#ifdef PORTABLE\n#include <stdio.h>\n#include "global.h"',1)
a=s.index('static void CB2_Exchange(void)');b=s.index('\nint WorldCoop_StartBattle(',a)
before=s[:a];part=s[a:b];after=s[b:]
part=part.replace('    u8 phase = sCoop.phase;','''    u8 phase = sCoop.phase;
    static u8 lastPhase = 255;
    if (phase != lastPhase) {
        fprintf(stderr, "coop-diag phase=%u local=%u link=%d status=%u finished=%d\\n", phase, sCoop.local, NativeLink_IsActive(), GetBlockReceivedStatus(), IsLinkTaskFinished());
        lastPhase = phase;
    }''')
lines=part.splitlines(keepends=True)
for i,line in enumerate(lines):
 if 'ExchangeFailed();' in line:
  indent=line[:len(line)-len(line.lstrip())]
  lines[i]=indent+f'fprintf(stderr, "coop-diag failure-site={i+1} phase=%u timer=%u status=%u finished=%d\\n", phase, sCoop.timer, GetBlockReceivedStatus(), IsLinkTaskFinished());\n'+line
p.write_text(before+''.join(lines)+after)
