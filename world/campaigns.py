"""Private short-run campaign director, not a native battle or save adapter.

Scenes, choices and recruitment execute here. Battle tickets require an owner
adapter using an isolated run profile; player controls cannot report victories.
"""
import hashlib
import json
from pathlib import Path
import re
import secrets


def _json(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def _id(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',value):raise ValueError('invalid campaign identifier')
    return value

def _text(value):
    if type(value) is not str or not 1<=len(value)<=240 or any(ord(c)<32 or ord(c)>126 for c in value):raise ValueError('campaign text must be 1..240 plain ASCII characters')


def validate(document):
    if type(document) is not dict or set(document)!={'title','start','members','initial','nodes'}:raise ValueError('invalid campaign definition')
    if len(_json(document))>65536:raise ValueError('campaign definition too large')
    _text(document['title']);_id(document['start'])
    species=set(json.loads(Path(__file__).with_name('expansion_species.json').read_text())['species'].values())
    def mon(m):
        if (type(m) is not dict or set(m)!={'species','level'} or type(m['species']) is not int or m['species'] not in species
                or type(m['level']) is not int or not 1<=m['level']<=100):raise ValueError('invalid campaign Pokemon')
    members=document['members'];nodes=document['nodes'];initial=document['initial']
    if type(members) is not dict or not 1<=len(members)<=12:raise ValueError('campaign needs 1..12 recruitable members')
    for identity,member in members.items():
        _id(identity)
        if type(member) is not dict or set(member)!={'name','mon'}:raise ValueError('invalid campaign member')
        _text(member['name']);mon(member['mon'])
    if (type(initial) is not list or not 1<=len(initial)<=3 or any(type(i) is not str or i not in members for i in initial)
            or len(set(initial))!=len(initial)):raise ValueError('initial rental squad needs 1..3 distinct members')
    if type(nodes) is not dict or not 2<=len(nodes)<=64:raise ValueError('campaign needs 2..64 nodes')
    edges={}
    for identity,node in nodes.items():
        _id(identity)
        if type(node) is not dict:raise ValueError('invalid campaign node')
        kind=node.get('kind');fields={'scene':{'next'},'choice':{'options'},'recruit':{'member','next'},'battle':{'enemy','next'},'end':set()}
        if kind not in fields or set(node)!={'kind','text'}|fields[kind]:raise ValueError('invalid campaign node fields')
        _text(node['text']);targets=[]
        if kind=='choice':
            options=node['options']
            if type(options) is not list or not 2<=len(options)<=4:raise ValueError('choice needs 2..4 options')
            keys=set()
            for option in options:
                if type(option) is not dict or set(option)!={'id','text','next'}:raise ValueError('invalid campaign option')
                key=_id(option['id']);_text(option['text'])
                if key in keys:raise ValueError('duplicate campaign option')
                keys.add(key);targets.append(option['next'])
        elif kind!='end':targets=[node['next']]
        if kind=='recruit' and node['member'] not in members:raise ValueError('unknown recruit')
        if kind=='battle':
            if type(node['enemy']) is not list or not 1<=len(node['enemy'])<=3:raise ValueError('battle needs 1..3 opponents')
            for item in node['enemy']:mon(item)
        for target in targets:
            if type(target) is not str or target not in nodes:raise ValueError('unknown campaign destination')
        edges[identity]=targets
    if document['start'] not in nodes:raise ValueError('unknown campaign start')
    visited=set();active=set()
    def walk(node):
        if node in active:raise ValueError('campaign branches must terminate; retry is handled by the director')
        if node in visited:return
        active.add(node)
        for target in edges[node]:walk(target)
        active.remove(node);visited.add(node)
    walk(document['start'])
    if visited!=set(nodes):raise ValueError('unreachable campaign nodes')
    return document


class Campaigns:
    def __init__(self,db):
        self.db=db
        db.executescript('''
            CREATE TABLE IF NOT EXISTS campaign_definitions (identity TEXT PRIMARY KEY, document TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS campaign_runs (id TEXT PRIMARY KEY, trainer TEXT NOT NULL, definition TEXT NOT NULL, revision INTEGER NOT NULL, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS campaign_requests (trainer TEXT, id TEXT, request TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(trainer,id));
            CREATE TABLE IF NOT EXISTS campaign_battles (ticket TEXT PRIMARY KEY, run TEXT NOT NULL, request TEXT NOT NULL, result TEXT);
        ''')

    def publish(self,document):
        validate(document);encoded=_json(document);identity=hashlib.sha256(encoded.encode()).hexdigest()
        with self.db:self.db.execute('INSERT OR IGNORE INTO campaign_definitions VALUES (?,?)',(identity,encoded))
        return dict(ok=True,definition=identity,title=document['title'],native_adapter='not_connected')

    def _run(self,trainer,identity):
        _id(identity)
        row=self.db.execute('SELECT definition,revision,state FROM campaign_runs WHERE id=? AND trainer=?',(identity,trainer)).fetchone()
        if row is None:raise ValueError('campaign run unavailable')
        doc=json.loads(self.db.execute('SELECT document FROM campaign_definitions WHERE identity=?',(row[0],)).fetchone()[0])
        return row[0],row[1],json.loads(row[2]),doc

    def _view(self,trainer,identity):
        definition,revision,state,doc=self._run(trainer,identity)
        return dict(ok=True,run=identity,definition=definition,revision=revision,title=doc['title'],state=state,
                    node=doc['nodes'][state['node']],members={k:doc['members'][k] for k in state['roster']},
                    native_adapter='not_connected',ownership='private run roster; normal trainer save is unchanged')

    def request(self,trainer,request):
        command=request.get('command')
        if command=='campaign_list' and set(request)=={'command'}:
            rows=self.db.execute('SELECT identity,document FROM campaign_definitions ORDER BY identity LIMIT 32').fetchall()
            return dict(ok=True,campaigns=[dict(definition=i,title=json.loads(d)['title']) for i,d in rows])
        if command=='campaign_runs' and set(request)=={'command'}:
            rows=self.db.execute('SELECT id,definition,revision,state FROM campaign_runs WHERE trainer=? ORDER BY rowid DESC LIMIT 32',(trainer,)).fetchall()
            return dict(ok=True,runs=[dict(run=i,definition=d,revision=r,status=json.loads(s)['status']) for i,d,r,s in rows])
        if command=='campaign_status' and set(request)=={'command','run'}:return self._view(trainer,request['run'])
        fields={'campaign_start':{'definition'},'campaign_act':{'run','expected_revision','action','value'}}
        if command not in fields or set(request)!={'command','request_id'}|fields[command]:raise ValueError('invalid campaign request')
        _id(request['request_id']);encoded=_json(request)
        receipt=self.db.execute('SELECT request,response FROM campaign_requests WHERE trainer=? AND id=?',(trainer,request['request_id'])).fetchone()
        if receipt:
            if receipt[0]!=encoded:raise ValueError('campaign request ID reused for another action')
            return dict(json.loads(receipt[1]),replayed=True)
        with self.db:
            if command=='campaign_start':
                if type(request['definition']) is not str or not re.fullmatch('[0-9a-f]{64}',request['definition']):raise ValueError('invalid campaign definition identity')
                row=self.db.execute('SELECT document FROM campaign_definitions WHERE identity=?',(request['definition'],)).fetchone()
                if not row:raise ValueError('campaign definition unavailable')
                pending=self.db.execute("SELECT id FROM campaign_runs WHERE trainer=? AND json_extract(state,'$.status') NOT IN ('completed','abandoned')",(trainer,)).fetchone()
                if pending:raise ValueError('finish or abandon your current campaign first')
                doc=json.loads(row[0]);identity=secrets.token_hex(16)
                state=dict(node=doc['start'],roster=doc['initial'][:],squad=doc['initial'][:],status='active',pending=None,last_result=None)
                self.db.execute('INSERT INTO campaign_runs VALUES (?,?,?,?,?)',(identity,trainer,request['definition'],0,_json(state)))
            else:
                identity=request['run'];definition,revision,state,doc=self._run(trainer,identity)
                if type(request['expected_revision']) is not int or request['expected_revision']!=revision:raise ValueError('campaign changed; refresh before acting')
                action,value=request['action'],request['value'];node=doc['nodes'][state['node']]
                if state['status'] in ('completed','abandoned'):raise ValueError('campaign has ended')
                if action=='abandon' and value is None:
                    if state['pending']:raise ValueError('resolve or abort the pending native battle before abandoning')
                    state['status']='abandoned'
                elif state['pending']:raise ValueError('native battle is pending; reconnect to the same ticket')
                elif action=='squad':
                    if (type(value) is not list or not 1<=len(value)<=3 or any(type(i) is not str or i not in state['roster'] for i in value)
                            or len(set(value))!=len(value)):raise ValueError('choose 1..3 recruited members')
                    state['squad']=value[:]
                elif action=='continue' and value is None and node['kind']=='scene':state['node']=node['next']
                elif action=='choose' and node['kind']=='choice':
                    option=next((o for o in node['options'] if o['id']==value),None)
                    if option is None:raise ValueError('unknown campaign choice')
                    state['node']=option['next']
                elif action=='recruit' and node['kind']=='recruit' and type(value) is bool:
                    if value and node['member'] not in state['roster']:state['roster'].append(node['member'])
                    state['node']=node['next']
                elif action=='battle' and value is None and node['kind']=='battle':
                    ticket=secrets.token_hex(16)
                    battle=dict(schema=1,ticket=ticket,run=identity,definition=definition,node=state['node'],
                                squad=[doc['members'][i]['mon'] for i in state['squad']],enemy=node['enemy'],
                                adapter='isolated_frontier_campaign_v1',evidence='battle_requested_not_started',
                                restrictions=['isolated_run_profile','no_normal_save_writes','no_frontier_rewards_or_streaks'])
                    self.db.execute('INSERT INTO campaign_battles VALUES (?,?,?,NULL)',(ticket,identity,_json(battle)))
                    state['pending']=battle;state['status']='battle_pending'
                elif action=='finish' and value is None and node['kind']=='end':state['status']='completed'
                else:raise ValueError('action does not apply to this campaign stage')
                self.db.execute('UPDATE campaign_runs SET revision=revision+1,state=? WHERE id=?',(_json(state),identity))
            result=self._view(trainer,identity)
            self.db.execute('INSERT INTO campaign_requests VALUES (?,?,?,?)',(trainer,request['request_id'],encoded,_json(result)))
        return result

    def report(self,request):
        """Owner-only adapter report. Never exposed as a player command or public history."""
        if set(request)!={'command','ticket','outcome'} or request['command']!='campaign_report' or request['outcome'] not in ('win','loss','abort'):
            raise ValueError('invalid campaign battle report')
        row=self.db.execute('SELECT run,request,result FROM campaign_battles WHERE ticket=?',(request['ticket'],)).fetchone()
        if row is None:raise ValueError('campaign battle ticket unavailable')
        if row[2]:
            previous=json.loads(row[2])
            if previous['outcome']!=request['outcome']:raise ValueError('campaign battle already has a different result')
            return dict(previous,replayed=True)
        owner=self.db.execute('SELECT trainer FROM campaign_runs WHERE id=?',(row[0],)).fetchone()[0]
        _,revision,state,doc=self._run(owner,row[0])
        if not state['pending'] or state['pending']['ticket']!=request['ticket']:raise ValueError('campaign battle is no longer pending')
        with self.db:
            state['pending']=None;state['status']='active';state['last_result']=request['outcome']
            if request['outcome']=='win':state['node']=doc['nodes'][state['node']]['next']
            self.db.execute('UPDATE campaign_runs SET revision=revision+1,state=? WHERE id=?',(_json(state),row[0]))
            result=dict(ok=True,ticket=request['ticket'],outcome=request['outcome'],run=row[0],revision=revision+1,
                        evidence='owner_adapter_report_not_independently_verified')
            self.db.execute('UPDATE campaign_battles SET result=? WHERE ticket=?',(_json(result),request['ticket']))
        return result
