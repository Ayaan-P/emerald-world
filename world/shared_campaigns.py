"""Optional private shared circuits. Results are client attestations, never shared story flags."""
import json
import secrets


def install(db):
    db.execute('CREATE TABLE IF NOT EXISTS shared_battle_runs(id TEXT PRIMARY KEY, data TEXT NOT NULL)')


def member(conn):
    return [conn['id'], conn['campaign_run']]


def load(server, key):
    row = server.db.execute('SELECT data FROM shared_battle_runs WHERE id=?', (key,)).fetchone()
    if not row:
        raise ValueError('Shared run unavailable')
    return json.loads(row[0])


def store(server, key, data):
    server.db.execute('INSERT OR REPLACE INTO shared_battle_runs VALUES(?,?)', (key, json.dumps(data)))


def update_members(server, key, group, **updates):
    for trainer, lineage in group['members']:
        row = server.db.execute('SELECT data FROM battle_campaign_runs WHERE trainer=? AND lineage=?', (trainer, lineage)).fetchone()
        if not row:
            raise ValueError('Shared member save binding unavailable')
        data = json.loads(row[0])
        if data.get('shared') != key:
            raise ValueError('Shared member save binding changed')
        data.update(updates)
        if 'node' in updates:data.pop('role',None)
        data.pop('preparation', None)
        server.db.execute('UPDATE battle_campaign_runs SET data=? WHERE trainer=? AND lineage=?', (json.dumps(data), trainer, lineage))


def command(server, conn, words, current):
    from .battle_campaigns import document, save
    me = member(conn)
    if len(words) == 2 and words[0] == 'share':
        if current and current[1]['status'] not in ('complete', 'withdrawn'):
            raise ValueError('Leave your current campaign first')
        doc = document(server, words[1]); key = secrets.token_hex(6)
        group = dict(campaign=doc['id'], members=[me], speaker=me, status='lobby', node=doc['entry'], results={}, advice={})
        with server.db:
            store(server, key, group)
            save(server, conn, doc['id'], dict(shared=key, node=doc['entry'], status='lobby', choices=[], history=[]))
        return True
    if len(words) == 2 and words[0] == 'join':
        if current and current[1]['status'] not in ('complete', 'withdrawn'):
            raise ValueError('Leave your current campaign first')
        key = words[1]; group = load(server, key)
        if group['status'] != 'lobby' or len(group['members']) >= 4 or any(m[0] == me[0] for m in group['members']):
            raise ValueError('Lobby closed, full, or trainer already joined')
        with server.db:
            group['members'].append(me); store(server, key, group)
            save(server, conn, group['campaign'], dict(shared=key, node=group['node'], status='lobby', choices=[], history=[]))
        return True
    if not current or not current[1].get('shared'):
        return False
    key = current[1]['shared']; group = load(server, key)
    from .campaign_regroup import command as regroup_command
    if regroup_command(server, conn, words, key, group):
        return True
    if words == ['begin']:
        if me != group['speaker'] or group['status'] != 'lobby' or len(group['members']) < 2:
            raise ValueError('Speaker can begin after 2–4 trainers join')
        from .parallel_campaigns import party_size,stage_status
        doc=document(server,group['campaign']);party_size(doc,len(group['members']))
        with server.db:
            group['status'] = stage_status(doc,group['node']);group['roles']={}; store(server, key, group)
            update_members(server, key, group, status=group['status'])
        return True
    if len(words)==2 and words[0]=='role':
        from .parallel_campaigns import choose
        choose(server,conn,key,group,words[1]);return True
    if len(words) == 2 and words[0] in ('choose', 'advise'):
        if group['status'] != 'choice' or words[1] not in group['choices']:
            raise ValueError('Choose an available shared route')
        if words[0] == 'advise':
            with server.db:
                group['advice'][conn['id']] = words[1]; store(server, key, group)
        else:
            if me != group['speaker']:
                raise ValueError('Only the speaker chooses; other trainers may advise')
            with server.db:
                from .parallel_campaigns import stage_status
                group.update(node=words[1], status=stage_status(document(server,group['campaign']),words[1]), results={}, advice={}, choices=[],roles={})
                store(server, key, group)
                update_members(server, key, group, node=words[1], status=group['status'], choices=[])
        return True
    if words == ['leave']:
        with server.db:
            group['status'] = 'cancelled'; store(server, key, group)
            for trainer, lineage in group['members']:
                existing=server.db.execute('SELECT data FROM battle_campaign_runs WHERE trainer=? AND lineage=?',(trainer,lineage)).fetchone()
                if existing and json.loads(existing[0]).get('shared')==key:
                    server.db.execute('DELETE FROM battle_campaign_runs WHERE trainer=? AND lineage=?', (trainer, lineage))
        return True
    if group['status']=='complete':
        return False
    if words and words[0] in ('start', 'share', 'join'):
        raise ValueError('Leave this shared run first')
    return False


def result(server, conn, key, data, pending, outcome):
    """Inside the existing exact nonce/save-bound battle result transaction."""
    from .battle_campaigns import document, save
    record=dict(node=data['node'],opponent=pending['id'],version=pending['version'],outcome=outcome,basis='client_attested')
    complete_stage(server,conn,key,data,outcome,record)


def complete_stage(server,conn,key,data,outcome,record):
    from .battle_campaigns import document,save,routes
    shared = data['shared']; group = load(server, shared)
    if group['status'] != 'ready' or member(conn) not in group['members'] or conn['id'] in group['results']:
        raise ValueError('Shared stage is no longer available')
    if data.get('role'):record=dict(record,role=data['role'])
    group['results'][conn['id']] = outcome
    data['history'].append(record)
    data.update(status='waiting', choices=[]); save(server, conn, key, data)
    if len(group['results']) == len(group['members']):
        outcome_key = 'win' if all(v == 1 for v in group['results'].values()) else 'loss'
        choices = routes(document(server,key)['nodes'][group['node']],outcome_key)
        group.update(choices=choices, status='choice' if choices else 'complete')
        update_members(server, shared, group, status=group['status'], choices=choices)
    store(server, shared, group)


def rows(server, conn, current):
    if not current or not current[1].get('shared'):
        return []
    key = current[1]['shared']; group = load(server, key)
    out = [('Shared run '+key+' - '+group['status'], None),
           ('Joining shares battle reports and voluntary visit check-ins with this party only.', None),
           ('Independent tasks in split stages; ordinary stages are repeated by everyone. No verified wins or rewards.', None)]
    from .parallel_campaigns import rows as deployment_rows
    out.extend(deployment_rows(server,conn,current,group))
    if group['status'] == 'lobby':
        out.append(('Invite with /guild campaign join '+key, None))
        out.append(('Joined trainers '+str(len(group['members']))+' of 4', None))
        if member(conn) == group['speaker']:
            out.append(('Begin shared run', ['begin']))
    elif group['status'] == 'ready':
        out.append(('Stage reports '+str(len(group['results']))+' of '+str(len(group['members'])), None))
    elif group['status'] == 'choice':
        for choice in group['choices']:
            out.append(('Advise route '+choice, ['advise', choice]))
        for trainer, choice in sorted(group['advice'].items()):
            out.append((trainer+' advises '+choice, None))
    from .campaign_regroup import rows as regroup_rows
    out.extend(regroup_rows(conn, group))
    return out
