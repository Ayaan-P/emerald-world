"""Distinct participants, actual admitted move contributions, existing object executor."""
import copy

def ready(needs,ledger):
    def match(index,used):
        if index==len(needs):return True
        key=needs[index]['object']+'/'+needs[index]['action']
        return any(p not in used and match(index+1,used|{p}) for p in ledger.get(key,[]))
    return match(0,set())

def validate(node,ids):
    gates=node.get('cooperate',{})
    if type(gates) is not dict or set(gates)-set(ids):raise ValueError('Cooperative gates name network members')
    total=0;keys=set()
    for obj,actions in gates.items():
        if type(actions) is not dict or set(actions)-set(node['on'].get(obj,{})):raise ValueError('Gate requires an authored action')
        for action,needs in actions.items():
            total+=1
            if type(needs) is not list or not 2<=len(needs)<=4:raise ValueError('Require two to four distinct participants')
            if node['use'].get(obj)==action:raise ValueError('Cooperative completion requires explicit choice')
            for need in needs:
                if type(need) is not dict or set(need)!={'object','action'} or type(need['object']) is not str or type(need['action']) is not str:raise ValueError('Contribution requires object/action')
                o,a=need['object'],need['action'];keys.add(o+'/'+a)
                if o not in ids or a not in node.get('moves',{}).get(o,{}):raise ValueError('Contribution must require a real learned move')
    if total>4 or len(keys)>4:raise ValueError('At most four gates and contribution action types per phase')

def visible_actions(node,obj,ledger):
    return {a:t for a,t in node['on'].get(obj,{}).items() if ready(node.get('cooperate',{}).get(obj,{}).get(a,[]),ledger)}

def prepare(server,request):
    for key,network in server.module_state.get('world_object_networks',{}).items():
        if request['object'] not in network['objects']:continue
        previous=server.module_state.get('world_object_controls',{}).get(request['object'],{}).get('state',{})
        phase=previous.get('phase',network['program']['initial']);node=network['program']['states'][phase]
        if not any(n.get('cooperate') for n in network['program']['states'].values()):return
        ledger=copy.deepcopy(previous.get('cooperators',{}));obj=request['object'];action=request['action']
        if not ready(node.get('cooperate',{}).get(obj,{}).get(action,[]),ledger):raise ValueError('Distinct participants must first commit the required moves')
        needs=[n for actions in node.get('cooperate',{}).values() for ns in actions.values() for n in ns]
        if dict(object=obj,action=action) in needs:
            evidence=request.get('move_effect',{})
            if request.get('player_choice') and evidence.get('basis')=='client_reported_learned_move':participant='player:'+evidence['trainer_id']
            elif request.get('actor') and evidence.get('basis')=='matching_native_move_inspection':participant='npc:'+request['actor']
            else:raise ValueError('Actual authorized move contribution required')
            if len(participant)>80:raise ValueError('Participant identity too long')
            entries=ledger.setdefault(obj+'/'+action,[])
            if participant not in entries and len(entries)<4:entries.append(participant)
        request['network_cooperation']=dict(network=key,definition=copy.deepcopy(network),previous=copy.deepcopy(previous),ledger=ledger)
        return

def inspect(server,obj):
    for key,network in server.module_state.get('world_object_networks',{}).items():
        if obj['id'] not in network['objects']:continue
        status=server.module_state.get('world_object_network_state',{}).get(key,{})
        node=network['program']['states'][status.get('phase',network['program']['initial'])]
        gates=node.get('cooperate',{})
        if not gates:return {}
        ledger=status.get('cooperators',{})
        return dict(network=key,phase=status['phase'],gates=[dict(object=o,action=a,ready=ready(needs,ledger),needs=needs) for o,actions in gates.items() for a,needs in actions.items()],contributions=copy.deepcopy(ledger),limits='Distinct authenticated player/NPC identities, not verified distinct humans. Only committed shared move actions count. Local PP actions are not evidence.')
    return {}


def remember(server,request):
    if 'network_cooperation' not in request:return
    import json
    server.db.execute('CREATE TABLE IF NOT EXISTS cooperative_move_intents(id TEXT PRIMARY KEY,document TEXT NOT NULL)')
    record=dict(cooperation=request['network_cooperation'],object=request['object'],action=request['action'])
    server.db.execute('INSERT OR IGNORE INTO cooperative_move_intents VALUES(?,?)',(request['id'],json.dumps(record,sort_keys=True)))

def validate_projection(server,state,key,network,status,updates):
    if not any(n.get('cooperate') for n in network['program']['states'].values()):return
    if server is None:raise ValueError('Cooperative projection requires authority')
    import json
    prior=server.module_state.get('world_object_network_state',{}).get(key,dict(phase=network['program']['initial'],turn=0))
    old=server.module_state.get('world_object_networks',{}).get(key)
    if status!=prior or (old is not None and old!=network):raise ValueError('Cooperative state/definition cannot be authored as completion')
    if not updates:return
    if len(updates)!=1:raise ValueError('One actual cooperative contribution at a time')
    receipts=state.get('world_object_current_receipt',{})
    if len(receipts)!=1:raise ValueError('Actual object receipt required')
    identity=next(iter(receipts))
    if not server.db.execute("SELECT 1 FROM sqlite_master WHERE name='cooperative_move_intents'").fetchone():raise ValueError('No admitted-request evidence')
    row=server.db.execute('SELECT document FROM cooperative_move_intents WHERE id=?',(identity,)).fetchone()
    if not row:raise ValueError('Unknown cooperative request')
    r=json.loads(row[0]);c=r['cooperation']
    if c['network']!=key or c['definition']!=network or c['previous']!=prior:raise ValueError('Stale cooperative intent')
    target=network['program']['states'][prior['phase']]['on'][r['object']][r['action']]
    expected=dict(phase=target,turn=prior['turn']+1,cooperators=c['ledger'] if target==prior['phase'] else {})
    if updates[0]!=expected or receipts[identity].get('object')!=r['object'] or receipts[identity].get('action')!=r['action']:raise ValueError('Cooperative result differs from authorized request')
