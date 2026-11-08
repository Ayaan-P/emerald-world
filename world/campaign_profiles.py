"""Isolated per-run native handoff, built on existing offline profile ownership.

This prepares and validates the adapter boundary. An engine without the exact
campaign protocol is refused; it is never launched as an ordinary replacement.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from .launcher import game_command, profile_paths, ProfileLock
from .offline import _private_directory, offline_profile
from .world_library import WorldActivityLock, _directory

PROTOCOL='EW_CAMPAIGN 1'
EXPERIMENTAL_PROTOCOL='EW_CAMPAIGN_EXPERIMENTAL 1'
RESTRICTIONS=['isolated_run_profile','no_normal_save_writes','no_frontier_rewards_or_streaks']


def _read(path,limit=8192):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_nlink!=1
                or info.st_mode&0o077 or info.st_size>limit):raise ValueError('campaign file must be private, owned and regular')
        raw=stream.read(limit+1)
        if len(raw)>limit:raise ValueError('campaign file too large')
    return json.loads(raw)


def _freeze(path,value):
    if path.exists() or path.is_symlink():
        if _read(path)!=value:raise ValueError('campaign file already has different ownership or content')
        return
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(value,stream,sort_keys=True,separators=(',',':'),allow_nan=False)
        stream.flush();os.fsync(stream.fileno())


def validate_ticket(ticket):
    if (type(ticket) is not dict or set(ticket)!={'schema','ticket','run','definition','node','squad','enemy','adapter','evidence','restrictions'}
            or type(ticket['schema']) is not int or ticket['schema']!=1
            or ticket['adapter']!='isolated_frontier_campaign_v1'
            or ticket['evidence']!='battle_requested_not_started' or ticket['restrictions']!=RESTRICTIONS):
        raise ValueError('unsupported campaign ticket contract')
    for key,length in (('ticket',32),('run',32),('definition',64)):
        if type(ticket[key]) is not str or not re.fullmatch('[0-9a-f]{'+str(length)+'}',ticket[key]):raise ValueError('invalid campaign identity')
    if type(ticket['node']) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,32}',ticket['node']):raise ValueError('invalid campaign stage')
    species=set(json.loads(Path(__file__).with_name('expansion_species.json').read_text())['species'].values())
    for key in ('squad','enemy'):
        team=ticket[key]
        if type(team) is not list or not 1<=len(team)<=3:raise ValueError('campaign rental squad needs 1..3 members')
        for mon in team:
            if (type(mon) is not dict or set(mon)!={'species','level'} or type(mon['species']) is not int or mon['species'] not in species
                    or type(mon['level']) is not int or not 1<=mon['level']<=100):raise ValueError('invalid rental Pokemon')
    return ticket


@contextmanager
def campaign_profile(state_dir,trainer,ticket,*,seed_save=None):
    """Hold world and run-profile locks until the native process has exited.

    A seed is an explicit one-time copy. No normal profile is inferred or copied,
    and no merge-back path exists. The frozen manifest stays outside native mounts.
    """
    validate_ticket(ticket)
    state=Path(state_dir).absolute()
    if state.resolve()!=state:raise ValueError('campaign world cannot contain symlinks')
    profile_paths(state,trainer,engine='expansion-native') # validate before mutation
    with WorldActivityLock(state):
        if not state.is_dir():raise ValueError('campaign requires an existing world directory')
        _directory(state)
        runs=state/'.campaign-runs';_private_directory(runs)
        root=runs/ticket['run'];_private_directory(root)
        manifest=dict(schema=1,run=ticket['run'],definition=ticket['definition'],trainer=trainer,engine='expansion-native')
        # One lock for the run, even if another caller names a different trainer.
        with ProfileLock(root,'campaign'):
            _freeze(root/'owner.json',manifest)
            with offline_profile(root,trainer,seed_save,engine='expansion-native') as paths:
                ticket_path=root/('ticket-'+ticket['ticket']+'.json');_freeze(ticket_path,ticket)
                yield dict(root=root,state=root/'.offline',paths=paths,ticket=ticket_path,
                           result=paths['profile']/('result-'+ticket['ticket']+'.json'),identity=ticket['ticket'])


def _base_command(binary,prepared,display=None):
    return game_command(binary,prepared['state'],prepared['paths'],display,online=False,engine='expansion-native')


def adapter_command(binary,prepared,display=None,*,experimental=False):
    """Probe within the same network-isolated profile sandbox; no fallback."""
    probe=_base_command(binary,prepared)
    checked=subprocess.run(probe+['--campaign-protocol'],capture_output=True,text=True,timeout=5)
    accepted={PROTOCOL}
    if experimental:accepted.add(EXPERIMENTAL_PROTOCOL)
    if checked.returncode!=0 or checked.stdout.strip() not in accepted:
        raise ValueError('native campaign adapter unavailable; campaign launch refused')
    command=_base_command(binary,prepared,display)
    separator=command.index('--')
    command[separator:separator]=['--ro-bind',str(prepared['ticket']),str(prepared['ticket'])]
    return command+['--campaign-ticket',str(prepared['ticket']),'--campaign-result',str(prepared['result'])]


def result_report(prepared):
    result=_read(prepared['result'],1024)
    if (type(result) is not dict or set(result)!={'schema','ticket','outcome','party_restored'}
            or type(result['schema']) is not int or result['schema']!=1 or result['ticket']!=prepared['identity']
            or result['outcome'] not in ('win','loss','abort') or result['party_restored'] is not True):
        raise ValueError('campaign result does not confirm this ticket and party restoration')
    # Still an adapter report, never independent proof of a battle or restoration.
    return dict(command='campaign_report',ticket=result['ticket'],outcome=result['outcome'])


def run_battle(binary,state_dir,trainer,ticket,*,seed_save=None,display=None,experimental=False):
    """Hold the owned run profile throughout a foreground native battle process.

    Experimental binaries require explicit opt-in. Closing/resetting before a
    restored receipt is produced leaves the director ticket unresolved. This
    returns an owner-report payload; it never sends it or marks a battle won.
    """
    with campaign_profile(state_dir,trainer,ticket,seed_save=seed_save) as prepared:
        if prepared['result'].exists():
            return result_report(prepared) # recover a completed launch without replaying it
        command=adapter_command(binary,prepared,display,experimental=experimental)
        completed=subprocess.run(command,check=False)
        if completed.returncode!=0:
            raise ValueError('campaign process failed; ticket remains unresolved')
        return result_report(prepared)
