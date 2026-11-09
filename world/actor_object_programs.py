"""Agent-authored state machines on real props, using existing use admission."""
import ast,copy,hashlib,inspect,json,re

def program_step(result,request):
 import copy
 result=copy.deepcopy(result);state=result['state'];obj=request['object'];identity=obj['id'];program=request['program']
 programs=state.setdefault('world_object_programs',{})
 if identity not in programs and next((o for o in result.get('objects',[]) if o['id']==identity),None)!=obj:raise ValueError('Object changed before program admission')
 programs.setdefault(identity,request['digest'])
 if programs[identity]!=request['digest']:raise ValueError('Object program identity changed')
 control=state.get('world_object_controls',{}).get(identity,{}).get('state',{})
 phase=control.get('phase',program['initial']);node=program['states'][phase]
 state.setdefault('world_object_actions',{})[identity]={a:a for a in node['on']}
 defaults=state.setdefault('world_object_player_use',{})
 if node['use']:defaults[identity]=node['use']
 else:defaults.pop(identity,None)
 for target in result['objects']:
  if target['id']==identity:target.update(text=node['text'],gfx=node['gfx'])
 return result

def transition(identity,action,state,request):
 program=request['program'];node=program['states'][state.get('phase',program['initial'])]
 if action not in node['on']:raise ValueError('Object action unavailable in current state')
 phase=node['on'][action];next_node=program['states'][phase];obj=request['object']
 return dict(state=dict(phase=phase),x=obj['x'],y=obj['y'],gfx=next_node['gfx'],text=next_node['text'])

def install(server,actor,row,args):
 from .actor_runtime import Pending
 from .actor_observation import observe
 from .actor_objects import digest
 if set(args)!={'object','revision','program'} or type(args['program']) is not str or len(args['program'])>700:raise ValueError('Supply observed prop revision and bounded program JSON')
 try:program=json.loads(args['program'])
 except ValueError:raise ValueError('Invalid object program JSON')
 name=lambda s:type(s) is str and bool(re.fullmatch('[a-z][a-z0-9_]{0,15}',s))
 if type(program) is not dict or set(program)!={'initial','states'} or not name(program['initial']) or type(program['states']) is not dict or not 1<=len(program['states'])<=4 or program['initial'] not in program['states']:raise ValueError('Program needs initial state and one to four states')
 for key,node in program['states'].items():
  if not name(key) or type(node) is not dict or set(node)!={'text','gfx','on','use'}:raise ValueError('State requires text, gfx, action transitions and optional native use action')
  if type(node['text']) is not str or not 1<=len(node['text'])<=28 or any(not 32<=ord(c)<127 for c in node['text']) or type(node['gfx']) is not int or node['gfx'] not in (0,1):raise ValueError('Unsupported prop appearance')
  if type(node['on']) is not dict or len(node['on'])>4 or any(not name(a) or not name(target) or target not in program['states'] for a,target in node['on'].items()):raise ValueError('Transitions must name defined states')
  if type(node['use']) is not str or (node['use'] and node['use'] not in node['on']):raise ValueError('Native use must name an advertised transition or be empty')
 seen=observe(server,actor,row,dict(radius=4));entry=next((e for e in seen['entities'] if e['id']==args['object']),{})
 obj=next((o for o in server.objects if o['id']==args['object']),None)
 if not obj or obj.get('kind')!='prop' or entry.get('program_revision')!=args['revision']:raise ValueError('Observed unprogrammed prop required')
 if server.module_state.get('world_object_actions',{}).get(obj['id']) or obj['id'] in server.module_state.get('world_object_controls',{}) or obj['id'] in server.module_state.get('world_object_programs',{}):raise ValueError('Existing object behavior is preserved; choose an unprogrammed prop')
 if obj.get('portable'):raise ValueError('Program supports anchored props, not portable custody')
 if server.job is not None or server.deployment is not None or not server.candidate:raise ValueError('Idle current mechanic required')
 request=dict(object=copy.deepcopy(obj),program=program,digest=digest(program));suffix=digest(request)[:16]
 helper=inspect.getsource(program_step).replace('def program_step(',f'def _program_{suffix}(',1)
 handler=inspect.getsource(transition).replace('def transition(',f'def _transition_{suffix}(',1)
 old=server.candidate.source
 fallback='actor_interact' if any(isinstance(n,ast.FunctionDef) and n.name=='actor_interact' for n in ast.parse(old).body) else 'None'
 source=old+f'\n_program_previous_{suffix}=update\n_program_handler_{suffix}={fallback}\n'+helper+'\n'+handler+f'''
def update(context,state):
    if not state:
        import copy
        state=copy.deepcopy({server.module_state!r})
    return _program_{suffix}(_program_previous_{suffix}(context,state),{request!r})
def actor_interact(object_id,action,state):
    if object_id=={obj['id']!r}:return _transition_{suffix}(object_id,action,state,{request!r})
    if _program_handler_{suffix} is None:raise ValueError('Unknown object handler')
    return _program_handler_{suffix}(object_id,action,state)
'''
 if len(source.encode())>256*1024:raise ValueError('Consolidate mechanic source before installing programs')
 sha=hashlib.sha256(source.encode()).hexdigest();path=server.runtime.candidates/('program_'+sha+'.py')
 try:
  with path.open('x') as f:f.write(source)
 except FileExistsError:
  if path.is_symlink() or path.read_text()!=source:raise ValueError('Program source conflict')
 def dispatch():server.deployment=(None,path,None)
 return Pending(dict(object=obj['id'],digest=request['digest']),dispatch)

def poll(server,actor,row,pending):
 if server.module_state.get('world_object_programs',{}).get(pending['object'])!=pending['digest']:raise ValueError('Object program was not admitted')
 return dict(outcome='interactive_prop_program_admitted',object=pending['object'],program_digest=pending['digest'],semantics='Native A and agent use share current advertised transitions. No inventory, movement, rewards or fabricated interactions.')
