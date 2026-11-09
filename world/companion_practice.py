"""Host-only isolated NPC practice ledger. No live-world/player packet authority.

Snapshots are opaque full native Pokemon bytes, tied to one executable digest.
They are not portable saves and must never be silently migrated between builds.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import uuid


def state(line):
    parts=line.strip().split()
    if len(parts)!=8 or parts[0]!='STATE1':raise ValueError('Invalid native state response')
    if any(not re.fullmatch(r'[0-9]{1,10}',p) for p in parts[1:7]):raise ValueError('Invalid native state fields')
    size,species,level,personality,owner,exp=map(int,parts[1:7]);blob=parts[7]
    if (not 1<=size<=1500 or not 1<=species<=65535 or not 1<=level<=100
        or max(personality,owner)>0xffffffff or exp>1640000
        or len(blob)!=size*2 or not re.fullmatch('[0-9a-f]+',blob)):
        raise ValueError('Invalid native state bounds')
    return dict(size=size,species=species,level=level,personality=personality,owner=owner,exp=exp,blob=blob)


class Engine:
    def __init__(self,path,digest):
        self.path=Path(path).resolve(strict=True)
        if not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Exact executable SHA256 required')
        self.digest=digest
    def run(self,line):
        if hashlib.sha256(self.path.read_bytes()).hexdigest()!=self.digest:raise ValueError('Native executable changed')
        with tempfile.TemporaryDirectory(prefix='npc-practice-') as directory:
            result=subprocess.run([str(self.path),'--character-practice'],input=line+'\n',text=True,
                capture_output=True,timeout=30,cwd=directory,env={'LANG':'C','LC_ALL':'C'})
        if result.returncode or len(result.stdout)>4096:raise ValueError('Native practice failed; no state committed')
        return state(result.stdout)


class Ledger:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS companions(actor TEXT, individual TEXT, engine TEXT,
          revision INTEGER, state TEXT, PRIMARY KEY(actor,individual));
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, actor TEXT, individual TEXT,
          engine TEXT, revision INTEGER, source TEXT, steps INTEGER, cap INTEGER,
          status TEXT, result TEXT);
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_practice ON jobs(actor,individual)
          WHERE status IN ('queued','running');
        ''')
    def close(self):self.db.close()
    def get(self,actor,individual):
        row=self.db.execute('SELECT engine,revision,state FROM companions WHERE actor=? AND individual=?',(actor,individual)).fetchone()
        if not row:raise ValueError('Unknown companion')
        return dict(engine=row[0],revision=row[1],state=json.loads(row[2]))
    def initialize(self,actor,individual,species,level,personality,owner,engine):
        for value in (actor,individual):
            if not re.fullmatch('[A-Za-z0-9_-]{1,24}',value):raise ValueError('Stable fictional actor/individual ID required')
        values=(species,level,personality,owner)
        if any(type(v) is not int for v in values) or not 1<=species<=65535 or not 1<=level<=100 or not 0<=personality<=0xffffffff or not 0<=owner<=0xffffffff:
            raise ValueError('Invalid initial identity')
        result=engine.run('INIT1 '+' '.join(map(str,values)))
        if tuple(result[k] for k in ('species','level','personality','owner'))!=values:raise ValueError('Native identity mismatch')
        with self.db:self.db.execute('INSERT INTO companions VALUES(?,?,?,?,?)',(actor,individual,engine.digest,1,json.dumps(result,sort_keys=True)))
        return self.get(actor,individual)
    def queue(self,actor,individual,steps,cap):
        if type(steps) is not int or not 1<=steps<=1024 or type(cap) is not int or not 1<=cap<=100:raise ValueError('Bounded exercise required')
        row=self.get(actor,individual)
        if row['state']['level']>=cap:raise ValueError('Companion is already at practice cap')
        job=uuid.uuid4().hex
        with self.db:self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,NULL)',(job,actor,individual,row['engine'],row['revision'],json.dumps(row['state'],sort_keys=True),steps,cap,'queued'))
        return job
    def execute(self,job,engine):
        # Claim once before external work. Interrupted running jobs are never
        # silently replayed; host can inspect them and explicitly cancel.
        with self.db:
            changed=self.db.execute("UPDATE jobs SET status='running' WHERE id=? AND status='queued' AND engine=?",(job,engine.digest)).rowcount
            if changed!=1:raise ValueError('Job unavailable or wrong engine')
        row=self.db.execute('SELECT actor,individual,revision,source,steps,cap FROM jobs WHERE id=?',(job,)).fetchone()
        actor,individual,revision,source,steps,cap=row;before=json.loads(source)
        try:
            result=engine.run(f"STEP1 {before['size']} {steps} {cap} {before['blob']}")
            if (any(result[k]!=before[k] for k in ('size','species','personality','owner'))
                or not before['exp']<result['exp']<=before['exp']+steps
                or not before['level']<=result['level']<=cap):raise ValueError('Native practice result inconsistent with job')
            encoded=json.dumps(result,sort_keys=True)
            with self.db:
                if self.db.execute("SELECT status FROM jobs WHERE id=?",(job,)).fetchone()!=('running',):raise ValueError('Job cancelled')
                changed=self.db.execute('UPDATE companions SET revision=revision+1,state=? WHERE actor=? AND individual=? AND revision=? AND engine=? AND state=?',
                    (encoded,actor,individual,revision,engine.digest,source)).rowcount
                if changed!=1:raise ValueError('Companion changed; result refused')
                self.db.execute("UPDATE jobs SET status='completed',result=? WHERE id=?",(encoded,job))
        except Exception:
            with self.db:self.db.execute("UPDATE jobs SET status='failed' WHERE id=? AND status='running'",(job,))
            raise
        return self.get(actor,individual)
    def cancel(self,job):
        with self.db:self.db.execute("UPDATE jobs SET status='cancelled' WHERE id=? AND status IN ('queued','running')",(job,))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True);parser.add_argument('--engine',required=True);parser.add_argument('--sha256',required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('init');p.add_argument('actor');p.add_argument('individual')
    for key in ('species','level','personality','owner'):p.add_argument(key,type=int)
    p=sub.add_parser('practice');p.add_argument('actor');p.add_argument('individual');p.add_argument('steps',type=int);p.add_argument('cap',type=int)
    p=sub.add_parser('run');p.add_argument('job')
    p=sub.add_parser('cancel');p.add_argument('job')
    p=sub.add_parser('show');p.add_argument('actor');p.add_argument('individual')
    args=parser.parse_args();ledger=Ledger(args.db);engine=Engine(args.engine,args.sha256)
    try:
        if args.command=='init':result=ledger.initialize(args.actor,args.individual,args.species,args.level,args.personality,args.owner,engine)
        elif args.command=='practice':result={'job':ledger.queue(args.actor,args.individual,args.steps,args.cap)}
        elif args.command=='run':result=ledger.execute(args.job,engine)
        elif args.command=='cancel':ledger.cancel(args.job);result={'status':'cancelled_if_active'}
        else:result=ledger.get(args.actor,args.individual)
        print(json.dumps(result,sort_keys=True))
    finally:ledger.close()
if __name__=='__main__':main()
