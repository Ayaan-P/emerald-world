"""One-shot host dispatcher for retained fictional cast practice intentions.

Deployment gate: use only after the exact native binary's isolated entry has
been validated. No live world receipt publication or story-party replacement.
"""
import argparse
import hashlib
import json
import sqlite3
from .companion_practice import Ledger,Engine
from . import gm


def signature(world,actor,row,task):
    return hashlib.sha256(json.dumps([world,actor,row['version'],task],sort_keys=True).encode()).hexdigest()


def step(ledger,engine,request,*,validated_native=False,steps=256,cap=20):
    if not validated_native:raise ValueError('Isolated native entry must be validated before enabling dispatcher')
    if type(steps) is not int or not 1<=steps<=1024 or type(cap) is not int or not 1<=cap<=100:raise ValueError('Invalid host exercise budget')
    ledger.db.execute('''CREATE TABLE IF NOT EXISTS cast_practice_dispatch(
      world TEXT,actor TEXT,intention TEXT,signature TEXT,job TEXT,status TEXT,receipt TEXT,
      PRIMARY KEY(world,actor,intention))''')
    snapshot=request({'command':'cast_practice_intentions'})
    if snapshot.get('ok') is not True:raise ValueError('Cast intention source unavailable')
    world=snapshot['world_id']
    for actor,row in sorted(snapshot['actors'].items()):
        if ledger.db.execute('SELECT count(*) FROM cast_practice_dispatch WHERE world=? AND actor=?',(world,actor)).fetchone()[0]>=8:continue
        for task in row['intentions']:
            if task['kind']!='practice':continue
            key=(world,actor,task['id'])
            if ledger.db.execute('SELECT 1 FROM cast_practice_dispatch WHERE world=? AND actor=? AND intention=?',key).fetchone():continue
            individual=task['target'];sig=signature(world,actor,row,task)
            try:
                companion=ledger.get(actor,individual)
                if companion['engine']!=engine.digest:raise ValueError('Registered companion belongs to another native build')
                # Claim intention and queue its frozen companion atomically.
                with ledger.db:
                    ledger.db.execute('BEGIN IMMEDIATE')
                    job=ledger.queue(actor,individual,steps,cap)
                    ledger.db.execute('INSERT INTO cast_practice_dispatch VALUES(?,?,?,?,?,?,NULL)',(*key,sig,job,'running'))
            except (ValueError,sqlite3.IntegrityError) as exc:
                return dict(status='blocked',actor=actor,intention=task['id'],reason=str(exc))
            def still_current():
                fresh=request({'command':'cast_practice_intentions'})
                current=fresh.get('actors',{}).get(actor,{})
                retained=next((t for t in current.get('intentions',[]) if t.get('id')==task['id']),None)
                return (fresh.get('ok') is True and fresh.get('world_id')==world and retained is not None
                        and signature(world,actor,current,retained)==sig)
            class BoundEngine:
                digest=engine.digest
                def run(self,line):
                    if not still_current():raise ValueError('Character intention changed before practice')
                    output=engine.run(line)
                    if not still_current():raise ValueError('Character intention changed during practice')
                    return output
            try:
                after=ledger.execute(job,BoundEngine())
                receipt=dict(world_id=world,character_id=actor,intention=task['id'],individual=individual,
                    job=job,engine=engine.digest,source_revision=companion['revision'],result_revision=after['revision'],
                    source_state_hash=hashlib.sha256(json.dumps(companion['state'],sort_keys=True).encode()).hexdigest(),
                    result_state_hash=hashlib.sha256(json.dumps(after['state'],sort_keys=True).encode()).hexdigest(),
                    simulated_steps=steps,exp_added=after['state']['exp']-companion['state']['exp'],
                    before_level=companion['state']['level'],after_level=after['state']['level'],
                    basis='isolated_host_practice_result',publication='local_host_ledger_only')
                with ledger.db:ledger.db.execute('UPDATE cast_practice_dispatch SET status=?,receipt=? WHERE world=? AND actor=? AND intention=?',('completed',json.dumps(receipt,sort_keys=True),*key))
                return dict(status='completed_in_host_ledger',receipt=receipt)
            except Exception as exc:
                with ledger.db:ledger.db.execute('UPDATE cast_practice_dispatch SET status=? WHERE world=? AND actor=? AND intention=?',('failed',*key))
                return dict(status='failed',actor=actor,intention=task['id'],reason=str(exc))
    return dict(status='idle')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('db','engine','sha256','socket'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--validated-native',action='store_true',help='Operator attests exact binary passed isolated-entry QA; not a gameplay preference')
    parser.add_argument('--steps',type=int,default=256);parser.add_argument('--cap',type=int,default=20)
    args=parser.parse_args();ledger=Ledger(args.db)
    try:print(json.dumps(step(ledger,Engine(args.engine,args.sha256),lambda body:gm.admin_request(args.socket,body,30),validated_native=args.validated_native,steps=args.steps,cap=args.cap),sort_keys=True))
    finally:ledger.close()
if __name__=='__main__':main()
