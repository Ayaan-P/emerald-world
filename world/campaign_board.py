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
    if not current or current[1]['status']=='complete':
        if current:out.append(('Campaign finished. Reported battles '+str(len(current[1]['history'])),None))
        for key,text in server.db.execute('SELECT id,document FROM battle_campaigns ORDER BY id LIMIT 32'):
            out.append(('Start '+json.loads(text)['title'],['start',key]))
            out.append(('Host shared '+json.loads(text)['title'],['share',key]))
        if not out:out.append(('No campaigns published. A configured world author can create one.',None))
    else:
        key,data=current;d=document(server,key)
        out.append((d['title']+' - '+data['status'],None))
        if data['status'] in ('lobby','waiting'):
            pass
        elif data['status']=='choice':
            group=shared_campaigns.load(server,data['shared']) if data.get('shared') else None
            for node in data['choices'] if not group or shared_campaigns.member(conn)==group['speaker'] else []:
                out.append(('Take route '+node+' against '+d['nodes'][node]['opponent'],['choose',node]))
        else:
            node=d['nodes'][data['node']];actor=node['opponent']
            obj=next((o for o in server.objects if o['id']==actor),None)
            out.append(('Battle '+actor+(' at map %s %s tile %s %s'%(obj['group'],obj['num'],obj['x'],obj['y']) if obj else ' - currently away'),None))
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
