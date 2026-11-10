"""Learned-move requirements for existing shared prop actions, not battle simulation."""
import copy,json,secrets,time
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=1)
def move_names():
    return json.loads(Path(__file__).with_name('companion_move_names.json').read_text())['names']

from .guilds import GuildError


def requirements(server,obj):
    from .move_selectors import resolve
    return {a:resolve(v) for a,v in server.module_state.get('world_object_moves',{}).get(obj['id'],{}).items()}


def validate_node(node):
    value=node.get('moves',{})
    from .move_selectors import resolve
    if type(value) is not dict or set(value)-set(node['on']):raise ValueError('Move requirements name advertised actions')
    for selector in value.values():resolve(selector)
    if node.get('use') in value:raise ValueError('Move actions require explicit selection, never ordinary A default')


def authorize(server,request):
    needed=requirements(server,request['target']).get(request['action'])
    evidence=request.get('move_effect')
    if needed is None:
        if evidence:raise ValueError('Action has no advertised learned-move effect')
        return
    if not evidence or evidence.get('move') not in needed:raise ValueError('Select an actual learned move for this action')
    if request.get('player_choice'):
        if evidence.get('basis')!='client_reported_learned_move':raise ValueError('Player move provenance required')
    else:
        if evidence.get('basis')!='matching_native_move_inspection':raise ValueError('Native companion inspection required')
        prove_companion(server,request['actor'],evidence['individual'],evidence['move'])


def prove_companion(server,actor,individual,move):
    from .character_training import source
    current=source(server,actor,individual)
    if not current['trained']:raise ValueError('Companion requires reconciled native state')
    for raw, in server.db.execute('SELECT result FROM actor_move_requests WHERE actor=? AND individual=? AND token=? AND result IS NOT NULL',(actor,individual,current['token'])):
        receipt=json.loads(raw)
        if receipt.get('outcome')=='native_move_choices' and move in receipt.get('slots',[]):return
    raise ValueError('Inspect current native companion moves first; authored or stale moves are insufficient')


def use(server,actor,row,args):
    from .actor_objects import use as use_object
    if set(args)!={'object','action','object_revision','individual','move'} or type(args['move']) is not int:raise ValueError('Select an observed move action and actual companion')
    prove_companion(server,actor,args['individual'],args['move'])
    return use_object(server,actor,row,{k:args[k] for k in ('object','action','object_revision')},dict(move=args['move'],individual=args['individual'],character_id=actor,basis='matching_native_move_inspection'))


def command(server,conn,words):
    from . import actor_objects,object_choices
    obj=object_choices.facing(server,conn);offer=actor_objects.offers(server,obj)
    allowed=server.module_state.get('world_object_player_choices',{}).get(obj['id'],[])
    choices={a:m for a,m in requirements(server,obj).items() if a in allowed and a in offer.get('actions',{})}
    if words==['moves']:
        token=secrets.token_hex(6)
        conn['object_moves']=dict(token=token,object=obj['id'],revision=offer.get('object_revision'),choices=copy.deepcopy(choices),until=time.monotonic()+60)
        if not choices:return ['No player move actions here.']
        lines=[obj['text'],'Selected move/action becomes public shared-world history, not your party.',
               'Use /fieldmove PARTY_SLOT MOVE_SLOT TOKEN ACTION yes.']
        for action,moves in choices.items():
            from .move_selectors import describe
            label=describe(server.module_state['world_object_moves'][obj['id']][action])
            if label:
                lines.append(f'{token} {action}: '+label)
                continue
            prefix=f'{token} {action}: ';line=prefix
            for move in moves:
                label=move_names().get(str(move),'move')+' ('+str(move)+')'
                if len(line)+len(label)+2>120:lines.append(line.rstrip(', '));line=prefix
                line+=label+', '
            lines.append(line.rstrip(', '))
        return lines
    if len(words)!=4 or words[0]!='move' or not words[3].isdigit():raise GuildError('Inspect /guild object moves, then use /fieldmove with your learned move.')
    pending=conn.pop('object_moves',None);move=int(words[3]);action=words[2]
    if (not pending or pending['token']!=words[1] or pending['until']<time.monotonic() or pending['object']!=obj['id'] or pending['revision']!=offer.get('object_revision') or pending['choices']!=choices or move not in choices.get(action,[])):
        raise GuildError('Move action changed, expired or mismatched. Inspect again.')
    if server.job is not None or server.deployment is not None or getattr(server,'object_use_pending',None):raise GuildError('Object busy; inspect again shortly.')
    request=dict(actor='',version=0,object=obj['id'],action=action,target=copy.deepcopy(obj),actions=offer['actions'],player_choice=True,nonce=pending['token'],move_effect=dict(move=move,trainer_id=conn['id'],basis='client_reported_learned_move'))
    try:work=actor_objects.stage(server,request,position=tuple(conn['state'][2:4]))
    except ValueError as exc:raise GuildError(str(exc)) from None
    server.object_use_pending=dict(conn=conn,pending=work.data,action=action);work.dispatch()
    return ['Move effect submitted; no success until shared-world admission. No battle PP is consumed.']


def remember(server,request):
    if not request.get('move_effect'):return
    from .move_feedback import remember as remember_visual
    remember_visual(server,request)
    server.db.execute('CREATE TABLE IF NOT EXISTS world_move_intents(id TEXT PRIMARY KEY,object TEXT,action TEXT,evidence TEXT,seq INTEGER)')
    server.db.execute('INSERT OR IGNORE INTO world_move_intents VALUES(?,?,?,?,NULL)',(request['id'],request['object'],request['action'],json.dumps(request['move_effect'],sort_keys=True)))


def admitted(server,identity):
    if not server.db.execute("SELECT 1 FROM sqlite_master WHERE name='world_move_intents'").fetchone():return
    row=server.db.execute('SELECT object,action,evidence,seq FROM world_move_intents WHERE id=?',(identity,)).fetchone()
    if not row or row[3] is not None:return
    seq=server.memory.append('object_move_committed',dict(object=row[0],action=row[1],request=identity,**json.loads(row[2]),limits='Admitted shared prop effect; no battle, PP use, growth or independently verified player party asserted.'))
    server.db.execute('UPDATE world_move_intents SET seq=? WHERE id=?',(seq,identity));server.revision=seq
    from .move_feedback import committed
    committed(server,identity,seq,json.loads(row[2])['move'])
