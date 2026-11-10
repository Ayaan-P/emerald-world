"""Explicit public in-world speech to recurring NPCs, not private cast chat."""
import json,time,secrets
from .characters import records
from .guilds import GuildError


def install(db):
    db.execute('CREATE TABLE IF NOT EXISTS npc_speech_audience(speech INTEGER,trainer TEXT,session TEXT,heard INTEGER DEFAULT 0,answered INTEGER DEFAULT 0,PRIMARY KEY(speech,trainer))')
    db.execute('CREATE TABLE IF NOT EXISTS npc_public_speech(seq INTEGER PRIMARY KEY,actor TEXT,trainer TEXT,version INTEGER,text TEXT,status TEXT,reply TEXT,session TEXT,delivery TEXT)')


def nearby(server,conn,actor):
    from .region_characters import scoped
    from .character_walks import walking
    character=records(server.module_state).get(actor)
    obj=next((o for o in server.objects if o['id']==actor),None);state=conn.get('state')
    if (not character or character['status']!='active' or not obj or server.peers.get(conn.get('id')) is not conn
        or conn.get('closing') or not state or not state[6] or not 0<=time.monotonic()-conn.get('state_time',0)<=5
        or state[:2]!=[obj['group'],obj['num']] or abs(state[2]-obj['x'])+abs(state[3]-obj['y'])>2
        or not scoped(server,conn,obj,obj.get('region_revision')) or walking(server.module_state,actor)
        or conn.get('character_pending')):
        raise GuildError('Stand ready beside this NPC in the same place before speaking.')
    return character,obj


def command(server,conn,words):
    if words and words[0] in ('guide','join-guide','leave-guide'):
        from .npc_guidance import command as guide_command
        return guide_command(server,conn,words)
    if words and words[0] in ('walk-with','walk-stop'):
        from .npc_accompaniment import command as walk_command
        return walk_command(server,conn,words)
    if not words:return ['NPC speech is PUBLIC world history, visible to world agents and players. Do not enter personal information.',
        'Use /guild npc nearby, or /guild npc say-public ID MESSAGE. Agent replies are not guaranteed.',
        'An NPC may offer to lead a group: /guild npc guide ID, join-guide ID, or leave-guide.',
        'Invite a generated NPC to walk with you: /guild npc walk-with ID. Stop: /guild npc walk-stop.']
    if words==['nearby']:
        found=[]
        for actor,c in records(server.module_state).items():
            try:nearby(server,conn,actor)
            except GuildError:continue
            from .npc_guidance import discover
            guide=next((g for g in discover(server) if g['actor']==actor),None)
            found.append(actor+': '+c['name'].encode('ascii','replace').decode()+(' - guide offered; /guild npc guide '+actor if guide else ''))
        return ['Nearby recurring NPCs:']+(found or ['None nearby and ready.'])
    if len(words)<3 or words[0]!='say-public':raise GuildError('Use /guild npc say-public ID MESSAGE. Speech enters public world history.')
    actor=words[1];text=' '.join(words[2:])
    if not 1<=len(text)<=80 or any(not 32<=ord(c)<127 for c in text):raise GuildError('Use 1-80 printable characters of public fictional dialogue.')
    character,obj=nearby(server,conn,actor)
    if time.monotonic()-conn.get('npc_speech_time',-100)<5:raise GuildError('Give the character a moment before speaking again.')
    with server.db:
        seq=server.memory.append('player_addressed_character',dict(character_id=actor,character_version=character['version'],text=text,
            revision=obj.get('region_revision'),position=[obj['group'],obj['num'],obj['x'],obj['y']],
            publication='explicit_public_npc_speech',basis='authenticated_nearby_player_message',
            limits='Player dialogue, not a command to obey or evidence that its claims occurred. No trainer name or save fields published.'))
        session=conn.setdefault('npc_speech_session',secrets.token_hex(16))
        server.db.execute('INSERT INTO npc_public_speech VALUES(?,?,?,?,?,?,NULL,?,NULL)',(seq,actor,conn['id'],character['version'],text,'delivered',session))
        # Freeze only physically present authenticated sessions, not a guild roster.
        for peer in server.peers.values():
            try:nearby(server,peer,actor)
            except GuildError:continue
            token=peer.setdefault('npc_speech_session',secrets.token_hex(16))
            server.db.execute('INSERT INTO npc_speech_audience(speech,trainer,session) VALUES(?,?,?)',(seq,peer['id'],token))
    server.revision=seq;conn['npc_speech_time']=time.monotonic()
    return ['Public speech delivered to '+character['name'].encode('ascii','replace').decode()+'. The character decides whether and how to respond.']


def inbox(server):
    return {actor:[dict(receipt=seq,text=text,status=status,reply=reply) for seq,text,status,reply in server.db.execute('SELECT seq,text,status,reply FROM npc_public_speech WHERE actor=? ORDER BY seq DESC LIMIT 16',(actor,))] for actor in records(server.module_state)}


def reply(server,actor,row,args):
    if set(args)!={'speech','text'} or type(args['speech']) is not int or type(args['text']) is not str or not 1<=len(args['text'])<=80 or any(not 32<=ord(c)<127 for c in args['text']):raise ValueError('Reply to an actual public speech receipt with 1-80 printable characters')
    original=server.db.execute('SELECT trainer,status,reply FROM npc_public_speech WHERE seq=? AND actor=?',(args['speech'],actor)).fetchone()
    if not original:raise ValueError('Speech was not addressed to this character')
    if original[1]=='replied':
        if original[2]!=args['text']:raise ValueError('Existing reply cannot be rewritten')
        return dict(outcome='already_replied',speech=args['speech'])
    current=records(server.module_state).get(actor)
    if not current or current['status']!='active':raise ValueError('Character unavailable')
    seq=server.memory.append('character_replied_to_player',dict(character_id=actor,speech=args['speech'],text=args['text'],publication='public_npc_reply',basis='authority_character_action',limits='Public fictional reply, not a promise fulfilled or a verified event.'))
    server.db.execute("UPDATE npc_public_speech SET status='replied',reply=? WHERE seq=?",(args['text'],args['speech']))
    server.revision=seq
    return dict(outcome='public_npc_reply_committed',speech=args['speech'],reply_receipt=seq,limits='Public history committed; live chat is delivered after commit only if the same speaker session remains nearby.')


def flush(server):
    # Durable one-shot live delivery after commit. Never replay to new sessions.
    rows=server.db.execute("""SELECT a.speech,a.trainer,a.session,a.heard,a.answered,
        s.actor,s.text,s.reply,s.status FROM npc_speech_audience a
        JOIN npc_public_speech s ON s.seq=a.speech
        WHERE a.heard=0 OR (a.answered=0 AND s.status='replied')""").fetchall()
    for seq,trainer,session,heard,answered,actor,text,reply_text,status in rows:
        peer=server.peers.get(trainer);current=records(server.module_state).get(actor)
        valid=bool(peer and peer.get('npc_speech_session')==session and current)
        if valid:
            try:nearby(server,peer,actor)
            except GuildError:valid=False
        # Mark before network output: at-most-once, not guaranteed delivery.
        with server.db:
            server.db.execute('UPDATE npc_speech_audience SET heard=1,answered=? WHERE speech=? AND trainer=?',
                (int(status=='replied') or answered,seq,trainer))
        if valid:
            name=current['name'].encode('ascii','replace').decode()
            if not heard:server.guild_chat.message(peer,'World',('Visitor to '+name+': '+text)[:120])
            if status=='replied' and not answered:server.guild_chat.message(peer,'World',(name+': '+reply_text)[:120])
            server._queue(peer,server._snapshot(peer))
    # Preserve legacy pending replies and original speaker delivery semantics.
    for seq,actor,trainer,session,text in server.db.execute("SELECT seq,actor,trainer,session,reply FROM npc_public_speech WHERE status='replied' AND delivery IS NULL").fetchall():
        peer=server.peers.get(trainer)
        valid=bool(peer and peer.get('npc_speech_session')==session)
        if valid:
            try:nearby(server,peer,actor)
            except GuildError:valid=False
        has_audience=server.db.execute('SELECT 1 FROM npc_speech_audience WHERE speech=?',(seq,)).fetchone()
        with server.db:server.db.execute('UPDATE npc_public_speech SET delivery=? WHERE seq=?',('sent' if valid else 'not_nearby',seq))
        if valid and not has_audience:
            name=records(server.module_state)[actor]['name'].encode('ascii','replace').decode()
            server.guild_chat.message(peer,'World',(name+': '+text)[:120])
            server._queue(peer,server._snapshot(peer))


def relevant(event,actor):
    return event.get('event')=='player_addressed_character' and event.get('character_id')==actor and event.get('publication')=='explicit_public_npc_speech' and event.get('basis')=='authenticated_nearby_player_message'
