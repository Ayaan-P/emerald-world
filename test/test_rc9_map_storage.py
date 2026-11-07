"""Compile the production map-buffer declaration, not a parallel allocator."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'engines/expansion-native'

class MapStorage(unittest.TestCase):
    def section(self, portable, xl):
        source = (ENGINE/'src/fieldmap.c').read_text()
        declaration = source[source.index('struct ConnectionFlags'):source.index('EWRAM_DATA struct MapHeader')]
        code = '#include <stdint.h>\ntypedef uint8_t u8;typedef uint16_t u16;\n#define EWRAM_DATA __attribute__((section(".sbss")))\n#define ALIGNED(n) __attribute__((aligned(n)))\n#define MAX_MAP_DATA_SIZE '+('24576' if portable and xl else '10240')+'\n'+declaration
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'map.c').write_text(code)
            cmd=['cc','-c','-o',str(p/'map.o'),str(p/'map.c'),'-DGENERATED_WORLD_XL='+str(int(xl))]
            if portable:cmd.append('-DPORTABLE=1')
            subprocess.run(cmd,check=True,capture_output=True)
            symbols=subprocess.check_output(['readelf','-sW',str(p/'map.o')],text=True)
            symbol=next(line.split() for line in symbols.splitlines() if line.split() and line.split()[-1]=='sBackupMapData')
            sections=subprocess.check_output(['readelf','-SW',str(p/'map.o')],text=True)
            name=re.search(r'\[\s*'+symbol[6]+r'\]\s+(\S+)',sections).group(1)
            return name,int(symbol[2])

    def test_xl_uses_host_backing_not_fixed_ewram(self):
        section,size=self.section(True,True)
        self.assertNotEqual(section,'.sbss')
        self.assertEqual(size,49152)

    def test_default_native_retains_fixed_ewram(self):
        self.assertEqual(self.section(True,False),('.sbss',20480))

    def test_gba_retains_fixed_ewram_even_with_xl_flag(self):
        self.assertEqual(self.section(False,True),('.sbss',20480))
