#!/usr/bin/env python3
"""Apply the new presence slice to an untouched, pinned native Expansion tree."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from map_compat import compatible, source

DONOR='bb3fd057061cdd7e6a9e79b76abb41924ee44ecc'
ROOT=Path(__file__).resolve().parents[1]

def git(path,*args):
 return subprocess.run(['git','-C',str(path),*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout

def main():
 p=argparse.ArgumentParser();p.add_argument('donor',type=Path);a=p.parse_args();donor=a.donor.resolve(strict=True)
 if git(donor,'rev-parse','HEAD').decode().strip()!=DONOR:raise SystemExit('wrong Expansion revision')
 if git(donor,'status','--porcelain','--untracked-files=all').strip():raise SystemExit('Expansion checkout must be clean')
 world=json.loads((ROOT.parent/'data/maps/map_groups.json').read_text())
 expansion=json.loads((donor/'data/maps/map_groups.json').read_text())
 maps=compatible(world,expansion)
 files=[x for x in (ROOT/'overlay').rglob('*') if x.is_file()]
 # Reuse the existing World link machinery verbatim; only its build wrapper is new.
 reused={
  'src/platform/native_link.c':'src/world/native_link.c',
  'src/platform/link_transport.c':'src/world/link_transport.c',
  'include/platform/native_link.h':'include/platform/native_link.h',
  'include/platform/link_transport.h':'include/platform/link_transport.h',
  'include/platform/native_file.h':'include/platform/native_file.h',
 }
 for dst in reused.values():
  if (donor/dst).exists():raise SystemExit('reused file would overwrite donor: '+dst)
 for src in files:
  dst=donor/src.relative_to(ROOT/'overlay')
  if dst.exists():raise SystemExit('overlay would overwrite an existing donor file: '+str(dst))
 if (donor/'src/world/map_compat.c').exists():raise SystemExit('generated map compatibility file already exists')
 git(donor,'apply','--check',str(ROOT/'main-hook.patch'))
 git(donor,'apply','--check',str(ROOT/'native-link-hook.patch'))
 git(donor,'apply',str(ROOT/'main-hook.patch'))
 git(donor,'apply',str(ROOT/'native-link-hook.patch'))
 for src,dst in reused.items():
  target=donor/dst; target.parent.mkdir(parents=True,exist_ok=True)
  body=(ROOT.parent/src).read_text()
  target.write_text(('#define PORTABLE 1\n' if src.endswith('.c') else '')+body)
 for src in files:
  dst=donor/src.relative_to(ROOT/'overlay');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
 (donor/'src/world/map_compat.c').write_text(source(maps))
 print(f'Applied clean Expansion presence slice with {len(maps)} matching map IDs. Multiplayer and generated worlds remain incomplete.')
if __name__=='__main__':main()
