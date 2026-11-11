"""Private paged native board with single-use, state-bound action tokens."""
import hashlib,json,re,secrets,time
from .battle_campaigns import active,command,document
from .campaign_preparation import describe


def literal(text,limit=96):
    return ''.join(c if c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,'!?-" else ' ' for c in text)[:limit] or 'Campaign'


def state_key(server,conn):
    from .shared_campaigns import load
    current=active(server,conn)
    group=load(server,current[1]['shared']) if current and current[1].get('shared') else None
    return hashlib.sha256(json.dumps([current,group],sort_keys=True).encode()).hexdigest()


def rows(server,conn):
    current=active(server,conn)
    from . import shared_campaigns
    out=shared_campaigns.rows(server,conn,current)
    if not current or current[1]['status'] in ('complete', 'withdrawn'):
        if current:out.append((('Campaign withdrawn. Reported stages ' if current[1]['status']=='withdrawn' else 'Campaign finished. Reported stages ')+str(len(current[1]['history'])),None))
        for key,text in server.db.execute('SELECT id,document FROM battle_campaigns ORDER BY id LIMIT 32'):
            doc=json.loads(text);sizes=[len(n['roles']) for n in doc['nodes'].values() if 'roles' in n]
            if not sizes:out.append(('Start '+doc['title'],['start',key]))
            mixed=any('revision' in t.get('visit',{}) for n in doc['nodes'].values() for t in n.get('roles',{}).values())
            out.append(('Host shared '+doc['title']+(f' - {sizes[0]} '+('roles including optional NPC visits' if mixed else 'trainers') if sizes else ''),['share',key]))
        if not out:out.append(('No campaigns published. A configured world author can create one.',None))
    else:
        key,data=current;d=document(server,key)
        out.append((d['title']+' - '+data['status'],None))
        if data['status'] in ('lobby','waiting','deploying'):
            pass
        elif data['status']=='choice':
            group=shared_campaigns.load(server,data['shared']) if data.get('shared') else None
            for node in data['choices'] if not group or shared_campaigns.member(conn)==group['speaker'] else []:
                target=d['nodes'][node]
                label='Split party' if 'roles' in target else target['visit']['label'] if 'visit' in target else target['expedition']['label'] if 'expedition' in target else target['mechanism']['label'] if 'mechanism' in target else target['opponent']
                out.append(('Take route '+node+' - '+label,['choose',node]))
        else:
            from .parallel_campaigns import effective
            node=effective(server,key,data)
            if 'expedition' in node:
                from .field_expeditions import rows as expedition_rows
                out.extend(expedition_rows(server,data,node))
                out.append(('Cancel shared run for everyone' if data.get('shared') else 'Leave campaign.',['leave']))
                return out
            if 'mechanism' in node:
                from .campaign_mechanisms import rows as mechanism_rows
                out.extend(mechanism_rows(server,data,node))
                out.append(('Cancel shared run for everyone' if data.get('shared') else 'Leave campaign.',['leave']))
                return out
            if 'visit' in node:
                from .campaign_visits import describe as describe_visit
                out.extend((line,None) for line in describe_visit(node))
                out.append(('Check in here. Report this stage to your run party.',['check-in']))
                out.append(('Cancel shared run for everyone' if data.get('shared') else 'Leave campaign. Pokemon and story unchanged.',['leave']))
                return out
            actor=node['opponent']
            obj=next((o for o in server.objects if o['id']==actor),None)
            place=None
            if obj and obj.get('region_revision'):
                place=server.db.execute('SELECT label FROM generated_area_archive WHERE identity=?',(obj['region_revision'],)).fetchone()
            destination=(' in '+place[0]+' tile %s %s'%(obj['x'],obj['y']) if place else ' at map %s %s tile %s %s'%(obj['group'],obj['num'],obj['x'],obj['y'])) if obj else ' - currently away'
            out.append(('Battle '+actor+destination,None))
            for choice,p in node.get('preparation',{}).items():
                from .actor_shops import ITEMS
                from .actor_tutors import MOVES
                service=('Tutor '+MOVES[p['move']] if p['move'] else '')+(' Shop '+','.join(ITEMS[i] for i in p['items']) if p['items'] else '')
                out.append(('Prepare '+choice+' with '+p['actor']+' '+service,['prepare',choice]))
            if data.get('preparation'):
                for text in describe(server,data,node):
                    if text.startswith(('Selected ','Camp ','Region:','Camp actor')):out.append((text,None))
        out.append(('Cancel shared run for everyone' if data.get('shared') else 'Leave campaign. Pokemon and story unchanged.',['leave']))
    return out


def handle(server,conn,run,key,guard):
    if conn.get('campaign_run')!=run:raise ValueError('Synchronize active save first')
    if key=='pick':
        pending=conn.pop('campaign_board',None)
        if not pending or pending['token']!=guard or pending['run']!=run or pending['until']<time.monotonic() or pending['state']!=state_key(server,conn) or not pending['command']:raise ValueError('Campaign option expired')
        command(server,conn,pending['command']);page=0
    elif key=='view' and re.fullmatch('[0-9]{1,2}',guard):page=int(guard)
    else:raise ValueError('Invalid campaign board action')
    choices=rows(server,conn);page%=len(choices);text,action=choices[page]
    token=secrets.token_hex(16)
    conn['campaign_board']=dict(token=token,command=action,run=run,state=state_key(server,conn),until=time.monotonic()+60)
    return dict(world=server.memory.world_id,page=page,total=len(choices),token=token,text=literal(text),label='Enter select' if action else 'Information')
