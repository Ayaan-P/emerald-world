"""Opt-in branching circuits over actual native NPC battles, not a battle simulator."""
import json
import re


def install(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS battle_campaigns(id TEXT PRIMARY KEY, actor TEXT, document TEXT);
    CREATE TABLE IF NOT EXISTS battle_campaign_runs(trainer TEXT, lineage TEXT, campaign TEXT, data TEXT,
      PRIMARY KEY(trainer,lineage));''')


def publish(server, actor, row, args):
    from .characters import records
    if set(args)!={'campaign'} or type(args['campaign']) is not str or len(args['campaign'])>6000:raise ValueError('Supply campaign JSON')
    d=json.loads(args['campaign']);cast=records(server.module_state)
    if type(d) is not dict or set(d)!={'id','title','entry','nodes'}:raise ValueError('Use id/title/entry/nodes')
    if type(d['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',d['id']):raise ValueError('Invalid campaign ID')
    if type(d['title']) is not str or not 1<=len(d['title'])<=48 or any(not 32<=ord(c)<127 for c in d['title']):raise ValueError('Invalid title')
    nodes=d['nodes']
    if type(nodes) is not dict or not 1<=len(nodes)<=16 or type(d['entry']) is not str or d['entry'] not in nodes:raise ValueError('Use 1..16 nodes and an entry')
    for key,n in nodes.items():
        if not re.fullmatch('[a-z][a-z0-9_]{0,15}',key) or type(n) is not dict or set(n)!={'opponent','win','loss'}:raise ValueError('Invalid battle node')
        if type(n['opponent']) is not str or n['opponent'] not in cast or not cast[n['opponent']]['team']:raise ValueError('Opponent must be an existing world trainer with a team')
        for outcome in ('win','loss'):
            edges=n[outcome]
            if type(edges) is not list or len(edges)>4 or any(type(x) is not str or x not in nodes for x in edges) or len(set(edges))!=len(edges):raise ValueError('Invalid route choices')
    seen=set();visiting=set()
    def visit(k):
        if k in visiting:raise ValueError('Campaign graph must be acyclic')
        if k in seen:return
        visiting.add(k)
        for target in nodes[k]['win']+nodes[k]['loss']:visit(target)
        visiting.remove(k);seen.add(k)
    visit(d['entry'])
    if seen!=set(nodes):raise ValueError('All nodes must be reachable')
    encoded=json.dumps(d,sort_keys=True,separators=(',',':'))
    old=server.db.execute('SELECT actor,document FROM battle_campaigns WHERE id=?',(d['id'],)).fetchone()
    if old and tuple(old)!=(actor,encoded):raise ValueError('Published campaign identities are immutable')
    server.db.execute('INSERT OR IGNORE INTO battle_campaigns VALUES(?,?,?)',(d['id'],actor,encoded))
    return dict(outcome='battle_campaign_published',campaign=d['id'],nodes=len(nodes),basis='Optional native battles; private client-attested progress, no rewards or simulated results')


def active(server,conn):
    lineage=conn.get('campaign_run')
    if not lineage:return None
    row=server.db.execute('SELECT campaign,data FROM battle_campaign_runs WHERE trainer=? AND lineage=?',(conn['id'],lineage)).fetchone()
    return (row[0],json.loads(row[1])) if row else None


def save(server,conn,campaign,data):
    server.db.execute('INSERT OR REPLACE INTO battle_campaign_runs VALUES(?,?,?,?)',(conn['id'],conn['campaign_run'],campaign,json.dumps(data)))


def document(server,key):
    row=server.db.execute('SELECT document FROM battle_campaigns WHERE id=?',(key,)).fetchone()
    if not row:raise ValueError('Unknown battle campaign')
    return json.loads(row[0])


def command(server,conn,words):
    from .guilds import GuildError
    try:
        if not words or words==['list']:
            return ['Battle campaigns:']+[f'{k}: {json.loads(d)["title"]}' for k,d in server.db.execute('SELECT id,document FROM battle_campaigns ORDER BY id LIMIT 32')]
        if not conn.get('campaign_run'):raise ValueError('Synchronize the current save before starting a campaign')
        if conn.get('character_pending'):raise ValueError('Finish the current battle first')
        current=active(server,conn)
        if len(words)==2 and words[0]=='start':
            if current and current[1]['status']!='complete':raise ValueError('Leave the current campaign first')
            d=document(server,words[1]);data=dict(node=d['entry'],status='ready',choices=[],history=[])
            with server.db:save(server,conn,d['id'],data)
        elif words==['leave']:
            with server.db:server.db.execute('DELETE FROM battle_campaign_runs WHERE trainer=? AND lineage=?',(conn['id'],conn['campaign_run']))
            return ['Battle campaign left. Pokemon and normal story unchanged.']
        elif len(words)==2 and words[0]=='choose':
            if not current or current[1]['status']!='choice' or words[1] not in current[1]['choices']:raise ValueError('Choose one of the offered routes')
            key,data=current;data.update(node=words[1],status='ready',choices=[])
            with server.db:save(server,conn,key,data)
        elif words!=['status']:raise ValueError('Use /guild campaign list|start ID|status|choose NODE|leave')
        current=active(server,conn)
        if not current:return ['No active battle campaign.']
        key,data=current;d=document(server,key)
        if data['status']=='complete':return [d['title']+': finished.', 'Reported battles: '+str(len(data['history']))]
        if data['status']=='choice':return [d['title']+': choose your next opponent.', 'Routes: '+', '.join(data['choices']), 'Use /guild campaign choose NODE.']
        opponent=d['nodes'][data['node']]['opponent']
        obj=next((x for x in server.objects if x['id']==opponent),None)
        return ([d['title']+': '+data['node'], 'Approach '+opponent+' and choose Battle.', ('Location: map %s/%s tile %s,%s'%(obj['group'],obj['num'],obj['x'],obj['y'])) if obj else 'Opponent currently away; progress is retained.'] + (['Region: '+obj['region_revision']] if obj and obj.get('region_revision') else []))
    except (ValueError,TypeError,KeyError) as exc:raise GuildError(str(exc)) from None


def bind(server,conn,pending):
    current=active(server,conn)
    if not current or current[1]['status']!='ready':return
    key,data=current
    if document(server,key)['nodes'][data['node']]['opponent']==pending['id']:
        pending['campaign_binding']=[conn['campaign_run'],key,data['node'],len(data['history'])]


def result(server,conn,pending,outcome):
    """Called inside the same transaction as the exact nonce-bound report."""
    binding=pending.get('campaign_binding')
    if not binding or outcome not in (1,2):return # Native WON/LOST only, not cancellation/flee/draw.
    if conn.get('campaign_run')!=binding[0]:return
    current=active(server,conn)
    if not current:return
    key,data=current
    if [key,data['node'],len(data['history'])]!=binding[1:] or data['status']!='ready':return
    choices=document(server,key)['nodes'][data['node']]['win' if outcome==1 else 'loss']
    data['history'].append(dict(node=data['node'],opponent=pending['id'],version=pending['version'],outcome=outcome,basis='client_attested'))
    data.update(choices=choices,status='choice' if choices else 'complete')
    save(server,conn,key,data)
