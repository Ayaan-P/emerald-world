"""Bounded public cast invitations delivered privately to registered game contacts."""
import re,secrets,time


def install(db):
    db.executescript('''
      CREATE TABLE IF NOT EXISTS canonical_calls(
        trainer TEXT,run TEXT,actor TEXT,request TEXT,token TEXT,status TEXT,text TEXT,created REAL,
        PRIMARY KEY(trainer,run,actor,request));
      CREATE TABLE IF NOT EXISTS canonical_call_settings(
        trainer TEXT,run TEXT,enabled INTEGER,PRIMARY KEY(trainer,run));
    ''')


def validate(actor,call):
    if call is None:return
    if (actor not in ('canon_wally','canon_steven') or type(call) is not dict or set(call)!={'id','text'}
            or type(call['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',call['id'])
            or type(call['text']) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,160}",call['text'])):
        raise ValueError('Call requests need an existing Wally/Steven contact, stable id and literal text')


def handle(server,conn,run,action,key,guard):
    if conn.get('core_active_run')!=run:raise ValueError('Calls require the current synchronized save')
    trainer=conn['id'];now=time.time()
    if action=='RSET' and key in ('on','off') and guard=='confirm':
        with server.db:server.db.execute('INSERT OR REPLACE INTO canonical_call_settings VALUES(?,?,?)',(trainer,run,int(key=='on')))
        return dict(ok=True)
    if action=='RACK' and guard in ('answer','decline','missed') and re.fullmatch('[0-9a-f]{32}',key):
        with server.db:
            row=server.db.execute('SELECT status FROM canonical_calls WHERE trainer=? AND run=? AND token=?',(trainer,run,key)).fetchone()
            if not row:raise ValueError('Unknown private call token')
            if row[0]=='offered':server.db.execute('UPDATE canonical_calls SET status=? WHERE trainer=? AND run=? AND token=?',(guard,trainer,run,key))
        return dict(ok=True)
    if action!='RING' or key not in ('1','2','3') or guard not in ('private','manual'):raise ValueError('Invalid call request')
    none=dict(caller='-',token='-',text='')
    if not conn.get('state') or not conn['state'][6] or not 0<=time.monotonic()-conn.get('state_time',0)<=3:return none
    setting=server.db.execute('SELECT enabled FROM canonical_call_settings WHERE trainer=? AND run=?',(trainer,run)).fetchone()
    if guard!='manual' and setting and not setting[0]:return none
    from .canonical_cast import records
    actors=records(server.module_state);mask=int(key)
    if guard=='manual':
        for actor,bit in (('canon_wally',1),('canon_steven',2)):
            call=(actors.get(actor) or {}).get('call')
            if not mask&bit or not call:continue
            old=server.db.execute('SELECT token,text,status FROM canonical_calls WHERE trainer=? AND run=? AND actor=? AND request=?',(trainer,run,actor,call['id'])).fetchone()
            if old and old[2]!='answer':
                with server.db:server.db.execute("UPDATE canonical_calls SET status='offered' WHERE trainer=? AND run=? AND token=?",(trainer,run,old[0]))
                return dict(caller=actor.removeprefix('canon_'),token=old[0],text=old[1])
    latest=server.db.execute('SELECT max(created) FROM canonical_calls WHERE trainer=? AND run=?',(trainer,run)).fetchone()[0]
    if guard!='manual' and latest is not None and now-latest<600:return none
    for actor,bit in (('canon_wally',1),('canon_steven',2)):
        call=(actors.get(actor) or {}).get('call')
        if not mask&bit or not call:continue
        old=server.db.execute('SELECT 1 FROM canonical_calls WHERE trainer=? AND run=? AND actor=? AND request=?',(trainer,run,actor,call['id'])).fetchone()
        if old:continue
        if server.db.execute('SELECT count(*) FROM canonical_calls WHERE trainer=? AND run=? AND actor=?',(trainer,run,actor)).fetchone()[0]>=32:continue
        token=secrets.token_hex(16)
        with server.db:
            server.db.execute('INSERT INTO canonical_calls VALUES(?,?,?,?,?,?,?,?)',(trainer,run,actor,call['id'],token,'offered',call['text'],now))
        return dict(caller=actor.removeprefix('canon_'),token=token,text=call['text'])
    return none
