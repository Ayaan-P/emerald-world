"""Exercise Linux's actual Makefile objcopy command with real ELF pointers."""
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(platform.system() == "Linux" and platform.machine() == "x86_64",
                     "requires Linux x86-64 ELF tools")
class LinuxDataRelocationsTests(unittest.TestCase):
    def test_assembled_pointer_survives_rename_and_is_read_only_after_relocation(self):
        for tool in ("make", "as", "objcopy", "readelf", "gcc"):
            if not shutil.which(tool):
                self.skipTest(f"requires {tool}")
        env = dict(os.environ, LC_ALL="C")
        # Do not inherit developer overrides of the command under test.
        for key in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES", "FIX_UNDERSCORE"):
            env.pop(key, None)

        def run(*args, **kwargs):
            return subprocess.check_output(args, text=True, env=env, **kwargs)

        with tempfile.TemporaryDirectory(prefix="linux-data-relocations-") as tmp:
            tmp = Path(tmp)
            command = run(
                "make", "--no-print-directory", "-s", "-f", "Makefile", "-f", "-",
                "PORTABLE=1", "TARGET_OS=LINUX", "IS64BIT=1", "NODEP=1",
                "SETUP_PREREQS=0", f"BUILD_DIR={tmp / 'build'}", "print-relocation-command",
                cwd=PROJECT,
                input=".PHONY: print-relocation-command\nprint-relocation-command:\n"
                      "\t@printf '%s\\n' '$(FIX_UNDERSCORE)'\n")
            source = tmp / "pointer.s"
            obj = tmp / "pointer.o"
            source.write_text('.section .rodata\n.balign 8\n.global pointer\n'
                              'pointer: .quad external_symbol\n'
                              '.section .note.GNU-stack,"",@progbits\n')
            run("as", "--64", "-o", str(obj), str(source))
            before = run("readelf", "-rW", str(obj))
            self.assertIn("R_X86_64_64", before)
            self.assertIn("external_symbol", before)
            run(*shlex.split(command.strip()), str(obj))
            after = run("readelf", "-rW", str(obj))
            self.assertIn("external_symbol", after,
                          f"Makefile command {command.strip()} lost the pointer relocation:\n{after}")
            self.assertIn("R_X86_64_64", after)
            self.assertIn(".rela.data.rel.ro", after)
            sections = run("readelf", "-SW", str(obj))
            self.assertRegex(sections, r"\.data\.rel\.ro\s+PROGBITS")

            # The loader must fix the pointer and then protect its page. Checking
            # /proc/self/maps catches a writable .data fallback as well as lost
            # relocations. No game, SDL, assets or personal saves are involved.
            main = tmp / "main.c"
            main.write_text(r'''
#include <stdint.h>
#include <stdio.h>
int external_symbol = 42;
extern int * const pointer;
int main(void) {
    if (pointer != &external_symbol || *pointer != 42) return 1;
    FILE *maps = fopen("/proc/self/maps", "r");
    if (!maps) return 2;
    char line[512], permissions[5];
    unsigned long start, end;
    uintptr_t address = (uintptr_t)&pointer;
    while (fgets(line, sizeof line, maps)) {
        if (sscanf(line, "%lx-%lx %4s", &start, &end, permissions) == 3 &&
            start <= address && address < end) {
            fclose(maps);
            return permissions[0] == 'r' && permissions[1] == '-' ? 0 : 3;
        }
    }
    fclose(maps);
    return 4;
}
''')
            exe = tmp / "pointer-test"
            run("gcc", "-fPIE", "-pie", "-Wl,-z,text,-z,relro,-z,now",
                str(main), str(obj), "-o", str(exe))
            headers = run("readelf", "-lW", str(exe))
            self.assertIn("GNU_RELRO", headers)
            self.assertNotIn("TEXTREL", run("readelf", "-dW", str(exe)))
            run(str(exe))


if __name__ == "__main__":
    unittest.main()
