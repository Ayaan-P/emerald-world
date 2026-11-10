"""Private solver turns, deliberately outside public actor plans and receipts.

Only trusted local host administration can claim/finish a turn. This module
never starts a provider, publishes private context, or authorizes public actions.
"""
import hashlib,json,re,secrets,time


def setup(db):
    db.execute('''CREATE TABLE IF NOT EXISTS private_mystery_partners(
      run TEXT PRIMARY KEY,actor TEXT,owner TEXT,message TEXT,status TEXT,lease TEXT,fingerprint TEXT,result TEXT)''')


def alias(actor):return '@npc:'+actor


def at(server,identity,point):
    if not identity.startswith('@npc:'):return False
    actor=identity[5:]
    from .characters import records
    from .character_walks import walking
    c=records(server.module_state).get(actor)
    obj=next((o for o in server.objects if o['id']==actor),None)
    return bool(c and c['status']=='active' and obj and not obj.get('region_revision')
        and not walking(server.module_state,actor)
        and tuple(point[:2]) not in (server.cave_map,server.wilds_map)
        and [obj['group'],obj['num'],obj['x'],obj['y']]==point)


def cancel(server,run):
    server.db.execute("UPDATE private_mystery_partners SET message='',status='cancelled',lease=NULL,fingerprint=NULL,result=NULL WHERE run=?",(run,))


def command(server,trainer,words):
    if not words or words[0] not in ('npc','npc-send','npc-status'):return None
    setup(server.db);m=server.mysteries
    if words==['npc']:
        return ['Private NPC partner: /mystery npc ACTOR reserves the second role for an existing generated NPC.',
                'The NPC must actually stand at its station. No canonical travel or automatic model call.',
                'After reading your clue: /mystery npc-send FICTIONAL MESSAGE. This shares it only with that NPC solver.',
                'The local host can access private data. No public history or general author context. Avoid personal information.',
                'Host must separately provide a private solver. /mystery npc-status shows results; /mystery leave cancels.']
    run=m._current(trainer) or (m._current(trainer,False) if words==['npc-status'] else None)
    if not run:raise ValueError('Start a mystery first')
    rid,key,stage,status,role=run
    if role!=0:raise ValueError('Only the initiating participant manages its NPC partner')
    if len(words)==2 and words[0]=='npc':
        pack=m._pack(key)
        if m._canonical(key) or len(pack['roles'])!=2:
            raise ValueError('Private NPC partners support only unbound two-role mysteries; this investigation needs human partners')
        actor=words[1];point=pack['stages'][stage]['stations'][1]['at']
        if status!='waiting' or not at(server,alias(actor),point):raise ValueError('A generated NPC must already stand at the second station of this waiting mystery')
        if server.db.execute("SELECT 1 FROM private_mystery_partners p JOIN mystery_runs r ON r.id=p.run WHERE p.actor=? AND r.status IN ('waiting','active')",(actor,)).fetchone():raise ValueError('NPC already participates in another mystery')
        server.db.execute('INSERT INTO mystery_members VALUES(?,1,?)',(rid,alias(actor)))
        server.db.execute("UPDATE mystery_runs SET status='active' WHERE id=?",(rid,))
        server.db.execute("INSERT INTO private_mystery_partners VALUES(?,?,?,'','idle',NULL,NULL,NULL)",(rid,actor,trainer))
        return ['NPC role reserved, not agent acceptance. The private solver may wait, solve or leave.',
                'Read your clue, then npc-send only the fictional information you want this NPC to receive.',
                'No model is started automatically; /mystery npc-status for progress.']
    p=server.db.execute('SELECT actor,status,result FROM private_mystery_partners WHERE run=? AND owner=?',(rid,trainer)).fetchone()
    if not p:raise ValueError('No NPC partner in this run')
    if words==['npc-status']:
        return ['Private NPC turn: '+p[1]]+(json.loads(p[2]) if p[2] else [])
    if len(words)>=2 and words[0]=='npc-send':
        message=' '.join(words[1:])
        if not 1<=len(message)<=120 or any(not 32<=ord(c)<127 for c in message):raise ValueError('Use 1..120 printable characters of fictional clue information')
        if p[1] in ('pending','claimed'):raise ValueError('A private turn is already pending; leave cancels it')
        pack=m._pack(key)
        if not m._at(trainer,pack['stages'][stage]['stations'][0]['at']) or not at(server,alias(p[0]),pack['stages'][stage]['stations'][1]['at']):raise ValueError('Both participants must actually be at their stations')
        if not server.db.execute('SELECT 1 FROM mystery_clues WHERE run=? AND stage=? AND role=0',(rid,stage)).fetchone():raise ValueError('Read your own clue first')
        server.db.execute("UPDATE private_mystery_partners SET message=?,status='pending',lease=NULL,fingerprint=NULL,result=NULL WHERE run=?",(message,rid))
        return ['Private fictional message queued only for this NPC solver. No public history or model call yet.']
    raise ValueError('Use npc ACTOR, npc-send MESSAGE, or npc-status')


def context(server,run,actor):
    m=server.mysteries
    row=server.db.execute('SELECT r.pack,r.stage,r.status,p.owner,p.message FROM mystery_runs r JOIN private_mystery_partners p ON p.run=r.id WHERE r.id=? AND p.actor=?',(run,actor)).fetchone()
    if not row or row[2]!='active':raise ValueError('Private partnership ended')
    key,stage,_,owner,message=row;pack=m._pack(key);part=pack['stages'][stage]
    if not at(server,alias(actor),part['stations'][1]['at']) or not m._at(owner,part['stations'][0]['at']):raise ValueError('Participants are not at their actual stations')
    from .characters import records
    c=records(server.module_state)[actor]
    # Deliberate allowlist: no trainer/run/save IDs, other clue, solution,
    # roster, general world inspection, source code or unrelated actor context.
    value=dict(actor=actor,name=c['name'],role=c['role'],stage=stage+1,task=pack['title'],station_clue=part['stations'][1]['clue'],partner_message=message,
               allowed=['wait','solve','leave'],limits='Private fictional partner turn. Return only action and answer; no public actions, dialogue, tools or world edits. A request is not success.')
    fingerprint=hashlib.sha256(json.dumps([value,c['version'],part['stations'][1]['at']],sort_keys=True).encode()).hexdigest()
    return value,fingerprint


def claim(server,actor,run):
    setup(server.db)
    with server.db:
        p=server.db.execute('SELECT status FROM private_mystery_partners WHERE run=? AND actor=?',(run,actor)).fetchone()
        if not p or p[0]!='pending':raise ValueError('No pending private turn for this actor and run')
        value,fingerprint=context(server,run,actor)
        server.mysteries.command(alias(actor),['clue'],transaction=False)
        lease=secrets.token_hex(24)
        server.db.execute("UPDATE private_mystery_partners SET status='claimed',lease=?,fingerprint=? WHERE run=?",(lease,fingerprint,run))
    return dict(ok=True,actor=actor,lease=lease,context=value)


def finish(server,actor,lease,decision):
    if type(decision) is not dict or set(decision)!={'action','answer'} or decision['action'] not in ('wait','solve','leave') or type(decision['answer']) is not str or (decision['action']=='solve' and not re.fullmatch('[A-Z0-9]{2,16}',decision['answer'])) or (decision['action']!='solve' and decision['answer']):raise ValueError('Private solver may only wait, leave, or submit a bounded answer')
    with server.db:
        saved=server.db.execute("SELECT run,fingerprint FROM private_mystery_partners WHERE actor=? AND lease=? AND status='claimed'",(actor,lease)).fetchone()
        if not saved:raise ValueError('Private lease is unavailable or already consumed')
        run,fingerprint=saved
        try:value,current=context(server,run,actor)
        except ValueError:
            cancel(server,run);return dict(ok=False,status='stale')
        if current!=fingerprint:
            cancel(server,run);return dict(ok=False,status='stale')
        if decision['action']=='wait':lines=['NPC chose to wait. You may send another private fictional message.']
        else:
            words=['leave'] if decision['action']=='leave' else ['solve',str(value['stage']),decision['answer']]
            lines=server.mysteries.command(alias(actor),words,transaction=False)
        server.db.execute("UPDATE private_mystery_partners SET status='finished',message='',lease=NULL,fingerprint=NULL,result=? WHERE run=?",(json.dumps(lines),run))
        return dict(ok=True,status='finished')


def process_one(server,actor,run,responder):
    """Trusted host adapter seam. Never calls a provider by itself or retries.

    The responder receives ONLY this private context; it must not be a public
    author pipeline. A failure leaves the claimed job unresolved, not replayable.
    """
    job=claim(server,actor,run)
    try:decision=responder(dict(job['context']))
    except Exception:raise ValueError('Private solver failed; claimed turn remains unresolved') from None
    return finish(server,actor,job['lease'],decision)
