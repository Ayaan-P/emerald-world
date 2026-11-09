"""Opt-in private encounter summaries backed by native display acknowledgments.

Client attestation, not proof of attention or an anti-cheat primitive.
"""
import hashlib
import json
import secrets
import time


def enabled(server, trainer, actor):
    return server.db.execute('SELECT 1 FROM canonical_memory_optin WHERE trainer=? AND actor=?',(trainer,actor)).fetchone() is not None


def prepare(server, conn, run, actor, row, response, map_name=None):
    if not enabled(server,conn['id'],actor):return response
    previous=server.db.execute('SELECT talks FROM canonical_encounters WHERE trainer=? AND run=? AND actor=?',(conn['id'],run,actor)).fetchone()
    if previous:
        response['briefing']='Good to see you again. '+response['briefing']
        response['objective']='' # Keep the complete literal response inside the native 240-byte limit.
    from .canonical_reflection import ready_record
    reflection=ready_record(server,conn['id'],actor,run,row['version'])
    response['receipt']=secrets.token_hex(16)
    response['digest']=hashlib.sha256(json.dumps(response,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    conn['cast_seen_pending']=dict(run=run,actor=actor,digest=response['digest'],expires=time.monotonic()+15,
                                   version=row['version'],goal=row['goal'],text=response['briefing'],map=map_name,
                                   reflection=reflection['id'] if reflection else None)
    return response


def acknowledge(server, conn, run, actor, digest, map_name=None):
    if not enabled(server,conn['id'],actor):return dict(ok=True)
    pending=conn.get('cast_seen_pending')
    if (not pending or pending['run']!=run or pending['actor']!=actor or pending['digest']!=digest
            or time.monotonic()>pending['expires']):raise ValueError('No matching displayed conversation receipt.')
    from .canonical_cast import BINDINGS
    expected=pending.get('map') or BINDINGS[actor]['map']
    if map_name is not None and map_name!=expected:raise ValueError('Display receipt location changed')
    server.core_story._place(conn,expected)
    now=time.time()
    with server.db:
        from .canonical_reflection import acknowledge_perspective
        acknowledge_perspective(server,conn,pending)
        server.db.execute('''INSERT INTO canonical_encounters VALUES(?,?,?,?,?,?,?,?)
          ON CONFLICT(trainer,run,actor) DO UPDATE SET talks=min(talks+1,65535),
          updated=excluded.updated,version=excluded.version,goal=excluded.goal,text=excluded.text''',
                          (conn['id'],run,actor,1,now,pending['version'],pending['goal'],pending['text']))
        server.db.execute('DELETE FROM canonical_encounters WHERE trainer=? AND actor=? AND rowid NOT IN (SELECT rowid FROM canonical_encounters WHERE trainer=? AND actor=? ORDER BY updated DESC LIMIT 16)',(conn['id'],actor,conn['id'],actor))
        server.db.execute('''DELETE FROM canonical_perspectives WHERE trainer=? AND actor=? AND run NOT IN
          (SELECT run FROM canonical_encounters WHERE trainer=? AND actor=?)''',(conn['id'],actor,conn['id'],actor))
    conn.pop('cast_seen_pending',None)
    return dict(ok=True)


def command(server, conn, actor, args):
    from .guilds import GuildError
    if args==['remember','on']:
        with server.db:server.db.execute('INSERT OR IGNORE INTO canonical_memory_optin VALUES(?,?)',(conn['id'],actor))
        return ['Private encounter memory enabled for this trainer and actor, separated by save lineage.',
                'Private conversation and partner encounter summaries only. No public history or shared author access.',
                'Use remember off to stop remembering, or forget to erase your choices and encounter summaries.']
    if args==['remember','off']:
        conn.pop('cast_partner_pending',None)
        with server.db:
            server.db.execute('DELETE FROM canonical_memory_optin WHERE trainer=? AND actor=?',(conn['id'],actor))
            server.db.execute('DELETE FROM canonical_decision_pending WHERE trainer=? AND actor=?',(conn['id'],actor))
            from .canonical_rapport import stop
            stop(server,conn['id'],actor)
            from .canonical_reflection import cancel
            cancel(server,conn['id'],actor)
        conn.pop('cast_seen_pending',None)
        return ['Encounter memory paused. Existing private summaries remain until you use forget.']
    if args==['memory']:
        rows=server.db.execute('SELECT talks,goal,text FROM canonical_encounters WHERE trainer=? AND actor=? ORDER BY updated DESC LIMIT 3',(conn['id'],actor)).fetchall()
        lines=['Private memory is '+('on.' if enabled(server,conn['id'],actor) else 'off.')]
        for i,(talks,goal,text) in enumerate(rows,1):
            lines.append(f'Save profile {i}: {talks} acknowledged conversations.')
            for label,value in [('Last actor goal: ',goal),('Last shown reply: ',text)]:
                value=label+value;lines.extend(value[j:j+110] for j in range(0,len(value),110))
        run=conn.get('core_active_run')
        from .canonical_decision_memory import context as decision_context
        for fact in decision_context(server,conn['id'],actor,run):
            lines.append('Shared conversation: you were '+fact['role']+'.')
            text='Your answer: '+fact['own_answer']+'; speaker chose: '+fact['speaker_answer']
            lines.extend(text[i:i+110] for i in range(0,len(text),110))
        from .canonical_partner_memory import context as partner_context
        for fact in partner_context(server,conn['id'],actor,run):
            lines.append('This save partner encounter: '+fact['outcome']+' (client report).')
        perspective=server.db.execute('SELECT interpretation FROM canonical_perspectives WHERE trainer=? AND actor=? AND run=?',(conn['id'],actor,run)).fetchone()
        if perspective:
            lines.append('Current save: the character\'s tentative perspective, not a fact about you.')
            lines.extend(perspective[0][i:i+110] for i in range(0,len(perspective[0]),110))
        return lines if rows else lines+['No acknowledged conversations retained.']
    raise GuildError('Use /guild cast ACTOR remember on|off, memory, or forget.')


def forget(server, conn, actor):
    from .canonical_rapport import stop
    stop(server,conn['id'],actor)
    from .canonical_reflection import cancel
    cancel(server,conn['id'],actor)
    conn.pop('cast_partner_pending',None)
    for table in ('canonical_partner_memory','canonical_memory_optin','canonical_encounters','canonical_perspectives','canonical_decision_pending','canonical_decision_memory'):
        server.db.execute(f'DELETE FROM {table} WHERE trainer=? AND actor=?',(conn['id'],actor))
    conn.pop('cast_seen_pending',None)
