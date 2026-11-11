"""Exact-engine move reminder jobs for world-owned companions, never player saves.

This local host ledger does not establish world authority by itself. Results must
be reconciled against the frozen authority source before being advertised in game.
"""
import json,re,uuid


def choices(line):
    fields=line.split()
    if len(fields)<6 or fields[0]!='MOVES1' or any(not re.fullmatch(r'[0-9]{1,5}',v) for v in fields[1:]):
        raise ValueError('Invalid native move choices')
    count=int(fields[1]);slots=list(map(int,fields[2:6]));moves=list(map(int,fields[6:]))
    if count!=len(moves) or count>2048 or len(set(moves))!=count or any(not 1<=m<=65535 or m in slots for m in moves) or any(m>65535 for m in slots):
        raise ValueError('Invalid native move choices')
    return dict(slots=slots,moves=moves)


class MoveJobs:
    def __init__(self,ledger):
        self.ledger=ledger;self.db=ledger.db
        self.db.execute('''CREATE TABLE IF NOT EXISTS companion_move_jobs(
          id TEXT PRIMARY KEY, actor TEXT, individual TEXT, engine TEXT,
          revision INTEGER, source TEXT, move INTEGER, slot INTEGER,
          status TEXT, result TEXT)''')
        self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_active_move_job ON companion_move_jobs(actor,individual) WHERE status IN ('queued','running')")

    def inspect(self,actor,individual,engine):
        row=self.ledger.get(actor,individual)
        if row['engine']!=engine.digest:raise ValueError('Companion belongs to another native build')
        before=row['state']
        return dict(revision=row['revision'],engine=engine.digest,**choices(engine.exchange(f"MOVES1 {before['size']} {before['blob']}")))

    def queue(self,actor,individual,revision,move,slot):
        if type(move) is not int or not 1<=move<=65535 or type(slot) is not int or not 0<=slot<4:raise ValueError('Choose native move and replacement slot')
        row=self.ledger.get(actor,individual)
        if row['revision']!=revision:raise ValueError('Companion choices are stale')
        if self.db.execute("SELECT 1 FROM jobs WHERE actor=? AND individual=? AND status IN ('queued','running')",(actor,individual)).fetchone():raise ValueError('Practice already pending')
        key=uuid.uuid4().hex
        with self.db:self.db.execute('INSERT INTO companion_move_jobs VALUES(?,?,?,?,?,?,?,?,?,NULL)',(key,actor,individual,row['engine'],revision,json.dumps(row['state'],sort_keys=True),move,slot,'queued'))
        return key

    def execute(self,key,engine):
        # The claim is durable before native execution. Crashed jobs are never
        # silently re-run. Their original source and result remain inspectable.
        with self.db:
            if self.db.execute("UPDATE companion_move_jobs SET status='running' WHERE id=? AND status='queued' AND engine=?",(key,engine.digest)).rowcount!=1:raise ValueError('Move job unavailable or wrong engine')
        actor,individual,revision,encoded,move,slot=self.db.execute('SELECT actor,individual,revision,source,move,slot FROM companion_move_jobs WHERE id=?',(key,)).fetchone()
        before=json.loads(encoded)
        try:
            current=self.ledger.get(actor,individual)
            if current!=dict(engine=engine.digest,revision=revision,state=before):raise ValueError('Companion changed before move learning')
            available=choices(engine.exchange(f"MOVES1 {before['size']} {before['blob']}"))
            if move not in available['moves']:raise ValueError('Move is not available from native reminder')
            result=engine.run(f"LEARN1 {before['size']} {move} {slot} {before['blob']}")
            if any(result[k]!=before[k] for k in ('size','species','level','personality','owner','exp')):raise ValueError('Move result changed identity or growth')
            updated=choices(engine.exchange(f"MOVES1 {result['size']} {result['blob']}"))
            expected=list(available['slots']);expected[slot]=move
            if updated['slots']!=expected:raise ValueError('Native move result differs from selected replacement')
            output=json.dumps(result,sort_keys=True)
            with self.db:
                if self.db.execute('UPDATE companions SET revision=revision+1,state=? WHERE actor=? AND individual=? AND revision=? AND engine=? AND state=?',(output,actor,individual,revision,engine.digest,encoded)).rowcount!=1:raise ValueError('Companion changed during move learning')
                self.db.execute("UPDATE companion_move_jobs SET status='completed',result=? WHERE id=?",(output,key))
        except Exception:
            with self.db:self.db.execute("UPDATE companion_move_jobs SET status='failed' WHERE id=? AND status='running'",(key,))
            raise
        return self.ledger.get(actor,individual)
