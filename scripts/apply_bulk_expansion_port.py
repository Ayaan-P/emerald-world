#!/usr/bin/env python3
"""Apply the provisional bulk port to a clean, exactly pinned donor checkout.

The patch carries mechanically merged World changes; named files are resolved
separately. Remaining conflicts still need resolution. Never use valuable saves.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

DONOR='bb3fd057061cdd7e6a9e79b76abb41924ee44ecc'
ROOT=Path(__file__).resolve().parents[1]
PORT=ROOT/'port'

def git(donor,*args,check=True):
    return subprocess.run(['git','-C',str(donor),*args],check=check,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

def apply(donor, patch):
    git(donor,'apply','--check','--binary',str(patch))
    git(donor,'apply','--binary',str(patch))

def merge_maps(donor):
    group_path=donor/'data/maps/map_groups.json'
    layout_path=donor/'data/layouts/layouts.json'
    groups=json.loads(group_path.read_text());layouts=json.loads(layout_path.read_text())
    key='gMapGroup_GeneratedWorld'
    if len(groups['group_order'])!=75 or key in groups or key in groups['group_order']:
        raise ValueError('donor map group layout changed; review before porting')
    if any(x['id'].startswith('LAYOUT_GENERATED_WORLD_') for x in layouts['layouts']):
        raise ValueError('generated layouts already exist; review before porting')
    # World authority uses group 34. Inserting the two maps preserves that
    # protocol identity but shifts later Expansion groups: old donor saves are
    # NOT compatible without migration, and fresh disposable profiles only.
    groups['group_order'].insert(34,key)
    groups[key]=['GeneratedWorld_Cave','GeneratedWorld_Wilds']
    for item in json.loads((PORT/'generated_layouts.json').read_text()):
        layouts['layouts'].append(dict(item,layout_version='emerald'))
    group_path.write_text(json.dumps(groups,indent=2)+'\n')
    layout_path.write_text(json.dumps(layouts,indent=2)+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('donor',type=Path);a=p.parse_args()
    donor=a.donor.resolve(strict=True)
    if git(donor,'rev-parse','HEAD').stdout.decode().strip()!=DONOR:
        raise SystemExit('wrong donor revision; no files were changed')
    if git(donor,'status','--porcelain','--untracked-files=all').stdout.strip():
        raise SystemExit('donor checkout must be clean; no files were changed')
    patches=sorted(PORT.glob('auto-engine-*.patch'))+[PORT/'world-runtime.patch']
    if len(patches)!=7:raise SystemExit('bulk source patches are incomplete')
    for patch in patches:apply(donor,patch)
    for source in sorted((PORT/'resolved').rglob('*')):
        if source.is_file():
            relative=source.relative_to(PORT/'resolved');target=donor/relative
            if not target.resolve().is_relative_to(donor):raise ValueError('resolution escapes donor')
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    merge_maps(donor)
    print('Applied provisional bulk port. Unresolved files remain; do not use valuable saves.')
if __name__=='__main__':main()
