#!/usr/bin/env python3
"""Reconstruct a bulk three-way source merge in a disposable directory.

The selected base is the vanilla native snapshot from which Emerald World was
created. The branches contain Emerald World and the native Expansion donor.
Unresolved files are kept at the donor version in the provisional patch and
listed explicitly. This produces a candidate, not a working game or release.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def run(args, *, cwd=None, check=True, stdout=subprocess.PIPE):
    return subprocess.run(args, cwd=cwd, check=check, stdout=stdout, stderr=subprocess.PIPE)

def git(work, *args, check=True):
    return run(['git', *args], cwd=work, check=check)

def export(repo, ref, destination):
    archive = subprocess.Popen(['git', '-C', str(repo), 'archive', ref], stdout=subprocess.PIPE)
    result = subprocess.run(['tar', '-x', '-C', str(destination)], stdin=archive.stdout, stderr=subprocess.PIPE)
    archive.stdout.close()
    if archive.wait() or result.returncode: raise RuntimeError('git archive failed')

def clear(work):
    for item in work.iterdir():
        if item.name == '.git': continue
        if item.is_dir() and not item.is_symlink(): shutil.rmtree(item)
        else: item.unlink()

def donor_copy(source, target):
    # Exclude the nested Git metadata and executable/ROM/save files; retain
    # game-source data, graphics and all regular build inputs.
    with tempfile.NamedTemporaryFile(suffix='.tar') as temp:
        run(['tar', '-c', '-f', temp.name, '--exclude=.git', '--exclude=*.gba',
             '--exclude=*.exe', '--exclude=*.sav', '-C', str(source), '.'])
        run(['tar', '-x', '-f', temp.name, '-C', str(target)])

def commit_tree(work, message):
    git(work, 'add', '-f', '-A')
    git(work, '-c', 'user.name=Bulk Port Probe', '-c', 'user.email=port-probe@invalid',
        'commit', '-q', '--allow-empty', '-m', message)
    return git(work, 'rev-parse', 'HEAD').stdout.decode().strip()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--donor', type=Path, required=True)
    p.add_argument('--base', required=True)
    p.add_argument('--world', required=True)
    p.add_argument('--output', type=Path, required=True)
    a=p.parse_args(); repo=a.repo.resolve(strict=True);donor=a.donor.resolve(strict=True)
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bulk-port-') as d:
        work=Path(d);git(work,'init','-q');export(repo,a.base,work)
        base=commit_tree(work,'Synthetic baseline')
        git(work,'checkout','-q','-b','world');clear(work);export(repo,a.world,work)
        world=commit_tree(work,'Emerald World source snapshot')
        git(work,'checkout','-q','-b','expansion',base);clear(work);donor_copy(donor,work)
        expansion=commit_tree(work,'Expansion source snapshot')
        changes=git(work,'diff','--name-only','-z',base,world).stdout.split(b'\0')
        merge=git(work,'-c','user.name=Bulk Port Probe','-c','user.email=port-probe@invalid',
                  'merge','--no-commit','--no-ff','world',check=False)
        if merge.returncode not in (0, 1):
            raise RuntimeError('bulk merge failed: '+merge.stderr.decode(errors='replace')[-4000:])
        unresolved=git(work,'diff','--name-only','--diff-filter=U','-z').stdout.split(b'\0')
        names=[os.fsdecode(x) for x in unresolved if x]
        # Keep the donor side only as a provisional fallback; every such path
        # is listed. Never claim these conflicts have been resolved.
        for name in names:
            exists=git(work,'cat-file','-e',':2:'+name,check=False).returncode==0
            if exists:
                git(work,'checkout','--ours','--',name);git(work,'add','-f','--',name)
            else:
                git(work,'rm','-f','--ignore-unmatch','--',name,check=False)
        remaining=git(work,'diff','--name-only','--diff-filter=U','-z').stdout
        if remaining.strip(b'\0'):raise RuntimeError('unresolved index entries remain')
        patch=git(work,'diff','--cached','--binary',expansion,'--','.',
                  ':(exclude)**/*.gba',':(exclude)**/*.exe',':(exclude)**/*.sav').stdout
        (out/'auto-merged.patch').write_bytes(patch)
        (out/'conflicts.txt').write_text(''.join(n+'\n' for n in names))
        summary={'baseline':a.base,'world':a.world,'donor':git(donor,'rev-parse','HEAD').stdout.decode().strip(),
                 'world_changed_paths':len([x for x in changes if x]),'conflicted_paths':len(names),
                 'merge_exit_code':merge.returncode,'patch_bytes':len(patch),
                 'warning':'Conflicted paths retain the Expansion side and require manual resolution; this is not a verified build.'}
        (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary,indent=2))
        print('Conflicted paths:\n'+'\n'.join(names))
if __name__=='__main__':main()
