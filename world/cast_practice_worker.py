"""One-shot host dispatcher for retained fictional cast practice intentions.

Deployment gate: use only after the exact native binary's isolated entry has
been validated. World-owned dynamic companions reconcile through local authority;
canonical story parties are never replaced.
"""
import argparse
import hashlib
import json
import sqlite3
import time
from .companion_practice import Ledger,Engine
from . import gm


def signature(world,actor,row,task):
    return hashlib.sha256(json.dumps([world,actor,row['version'],task],sort_keys=True).encode()).hexdigest()


def step(ledger,engine,request,*,validated_native=False,steps=256,cap=20,turn_limit=8,period_hours=24,now=None):
    if not validated_native:raise ValueError('Isolated native entry must be validated before enabling dispatcher')
    if type(steps) is not int or not 1<=steps<=1024 or type(cap) is not int or not 1<=cap<=100:raise ValueError('Invalid host exercise budget')
    ledger.db.execute('''CREATE TABLE IF NOT EXISTS cast_practice_dispatch(
      world TEXT,actor TEXT,intention TEXT,signature TEXT,job TEXT,status TEXT,receipt TEXT,
      PRIMARY KEY(world,actor,intention))''')
    if type(turn_limit) is not int or not 1<=turn_limit<=64 or type(period_hours) is not int or not 1<=period_hours<=168:raise ValueError('Invalid recurring host practice budget')
    now=time.time() if now is None else now
    ledger.db.execute('CREATE TABLE IF NOT EXISTS practice_budget(world TEXT,actor TEXT,started REAL,used INTEGER,PRIMARY KEY(world,actor))')
    snapshot=request({'command':'cast_practice_intentions'})
    if snapshot.get('ok') is not True:raise ValueError('Cast intention source unavailable')
    world=snapshot['world_id']
    for actor,row in sorted(snapshot['actors'].items()):
        budget=ledger.db.execute('SELECT started,used FROM practice_budget WHERE world=? AND actor=?',(world,actor)).fetchone()
        if budget and now<budget[0]+period_hours*3600 and budget[1]>=turn_limit:continue
        for task in row['intentions']:
            if task['kind']!='practice':continue
            key=(world,actor,task['id'])
            if ledger.db.execute('SELECT 1 FROM cast_practice_dispatch WHERE world=? AND actor=? AND intention=?',key).fetchone():continue
            individual=task['target'];sig=signature(world,actor,row,task)
            try:
                training_source=None
                if row.get('binding')=='world_character':
                    response=request(dict(command='character_practice_source',actor=actor,individual=individual))
                    if response.get('ok') is not True:raise ValueError('World companion source unavailable')
                    training_source=response['source']
                    if training_source['world_id']!=world or training_source['version']!=row['version']:raise ValueError('World companion changed')
                    try:ledger.get(actor,individual)
                    except ValueError:
                        if training_source['trained']:raise ValueError('Existing full world state requires explicit host recovery; do not recreate by level')
                        ledger.initialize(actor,individual,training_source['species'],training_source['authored_level'],training_source['personality'],training_source['owner'],engine)
                companion=ledger.get(actor,individual)
                if training_source and training_source['trained'] and (companion['engine']!=training_source['trained']['engine'] or companion['state']!=training_source['trained']['state']):raise ValueError('Local/world full companion state diverged')
                if companion['engine']!=engine.digest:raise ValueError('Registered companion belongs to another native build')
                # Claim intention and queue its frozen companion atomically.
                with ledger.db:
                    ledger.db.execute('BEGIN IMMEDIATE')
                    budget=ledger.db.execute('SELECT started,used FROM practice_budget WHERE world=? AND actor=?',(world,actor)).fetchone()
                    if budget and now<budget[0]+period_hours*3600 and budget[1]>=turn_limit:raise ValueError('Practice period budget exhausted')
                    started,used=(now,0) if not budget or now>=budget[0]+period_hours*3600 else budget
                    ledger.db.execute('INSERT INTO practice_budget VALUES(?,?,?,?) ON CONFLICT(world,actor) DO UPDATE SET started=excluded.started,used=excluded.used',(world,actor,started,used+1))
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
                status='completed_in_host_ledger'
                if training_source is not None:
                    payload=dict(command='character_practice_apply',actor=actor,individual=individual,token=training_source['token'],job=job,engine=engine.digest,before=companion['state'],after=after['state'],steps=steps,cap=cap)
                    if task.get('capability_request'):payload['capability_request']=task['capability_request']
                    receipt['authority_payload']=payload
                    with ledger.db:ledger.db.execute('UPDATE cast_practice_dispatch SET status=?,receipt=? WHERE world=? AND actor=? AND intention=?',('awaiting_reconciliation',json.dumps(receipt,sort_keys=True),*key))
                    applied=request(payload)
                    if applied.get('ok') is not True:raise ValueError('Practice completed locally but world reconciliation refused: '+str(applied.get('error')))
                    receipt.update(publication='public_fictional_character_practice',world_receipt=applied['seq'])
                    status='reconciled_to_world_companion'
                with ledger.db:ledger.db.execute('UPDATE cast_practice_dispatch SET status=?,receipt=? WHERE world=? AND actor=? AND intention=?',('completed',json.dumps(receipt,sort_keys=True),*key))
                return dict(status=status,receipt=receipt)
            except Exception as exc:
                with ledger.db:ledger.db.execute('UPDATE cast_practice_dispatch SET status=? WHERE world=? AND actor=? AND intention=?',('failed',*key))
                return dict(status='failed',actor=actor,intention=task['id'],reason=str(exc))
    return dict(status='idle')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('db','engine','sha256','socket'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--validated-native',action='store_true',help='Operator attests exact binary passed isolated-entry QA; not a gameplay preference')
    parser.add_argument('--steps',type=int,default=256);parser.add_argument('--cap',type=int,default=20)
    parser.add_argument('--turn-limit',type=int,default=8)
    parser.add_argument('--period-hours',type=int,default=24)
    args=parser.parse_args();ledger=Ledger(args.db)
    try:print(json.dumps(step(ledger,Engine(args.engine,args.sha256),lambda body:gm.admin_request(args.socket,body,30),validated_native=args.validated_native,steps=args.steps,cap=args.cap,turn_limit=args.turn_limit,period_hours=args.period_hours),sort_keys=True))
    finally:ledger.close()
if __name__=='__main__':main()
