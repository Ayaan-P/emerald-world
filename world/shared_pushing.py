"""Directional shared-object movement, not native inventory or HM Strength."""
import ast,copy,hashlib,inspect
from .actor_objects import digest


def projection(result,definition):
 import copy
 result=copy.deepcopy(result);state=result['state'];identity=definition['object']['id']
 saved=state.setdefault('world_pushables',{})
 if identity not in saved and next((o for o in result.get('objects',[]) if o['id']==identity),None)!=definition['object']:raise ValueError('Object changed before pushing admission')
 saved.setdefault(identity,definition['digest'])
 if saved[identity]!=definition['digest']:raise ValueError('Pushable definition changed')
 state.setdefault('world_object_actions',{})[identity]={'push':'Push from your side.'}
 state.setdefault('world_object_player_use',{})[identity]='push'
 control=state.get('world_object_controls',{}).get(identity,{}).get('object',{})
 for obj in result['objects']:
  if obj['id']==identity:obj.update(copy.deepcopy(control))
 return result


def handler(state,obj,vector):
 if type(vector) is not list or vector not in ([0,1],[0,-1],[1,0],[-1,0]):raise ValueError('No admitted push direction')
 x=state.get('x',obj['x'])+vector[0];y=state.get('y',obj['y'])+vector[1]
 return dict(state=dict(x=x,y=y),x=x,y=y,gfx=obj['gfx'],text=obj['text'])


def install(server,actor,row,args):
 from .actor_runtime import Pending
 from .actor_observation import observe
 if set(args)!={'object','revision'}:raise ValueError('Choose an observed unused anchored prop')
 seen=observe(server,actor,row,dict(radius=4));entry=next((e for e in seen['entities'] if e['id']==args['object']),{})
 obj=next((o for o in server.objects if o['id']==args['object']),None)
 if not obj or obj.get('kind')!='prop' or obj.get('portable') or entry.get('program_revision')!=args['revision']:raise ValueError('Choose an observed anchored prop at its exact revision')
 if any(obj['id'] in server.module_state.get(key,{}) for key in ('world_object_controls','world_object_programs','world_object_actions','world_pushables')):raise ValueError('Existing object behavior preserved')
 if server.db.execute("SELECT 1 FROM sqlite_master WHERE name='cave_links'").fetchone() and server.db.execute('SELECT 1 FROM cave_links WHERE object=?',(obj['id'],)).fetchone():raise ValueError('Existing passage preserved')
 if server.job is not None or server.deployment is not None or not server.candidate:raise ValueError('Idle current mechanic required')
 definition=dict(object=copy.deepcopy(obj),digest=digest(obj));suffix=definition['digest'][:16]
 old=server.candidate.source;fallback='actor_interact' if any(isinstance(n,ast.FunctionDef) and n.name=='actor_interact' for n in ast.parse(old).body) else 'None'
 project=inspect.getsource(projection).replace('def projection(',f'def _push_project_{suffix}(',1)
 handle=inspect.getsource(handler).replace('def handler(',f'def _push_handler_{suffix}(',1)
 source=old+f'\n_push_previous_{suffix}=update\n_push_fallback_{suffix}={fallback}\n_push_vector_{suffix}=[0,0]\n'+project+'\n'+handle+f'''
def update(context,state):
    if not state:
        import copy
        state=copy.deepcopy({server.module_state!r})
    return _push_project_{suffix}(_push_previous_{suffix}(context,state),{definition!r})
def actor_interact(object_id,action,state):
    if object_id=={obj['id']!r} and action=='push':return _push_handler_{suffix}(state,{obj!r},_push_vector_{suffix})
    if _push_fallback_{suffix} is None:raise ValueError('Unknown object action')
    return _push_fallback_{suffix}(object_id,action,state)
'''
 if len(source.encode())>256*1024:raise ValueError('Consolidate source before installing another body')
 sha=hashlib.sha256(source.encode()).hexdigest();path=server.runtime.candidates/('pushable_'+sha+'.py')
 try:
  with path.open('x') as f:f.write(source)
 except FileExistsError:
  if path.is_symlink() or path.read_text()!=source:raise ValueError('Pushable candidate conflict')
 def dispatch():server.deployment=(None,path,None)
 return Pending(definition,dispatch)


def poll_install(server,actor,row,pending):
 obj=next((o for o in server.objects if o['id']==pending['object']['id']),None)
 if obj!=pending['object'] or server.module_state.get('world_pushables',{}).get(obj['id'])!=pending['digest']:raise ValueError('Pushable was not admitted')
 return dict(object=obj['id'],outcome='directional_pushing_enabled',revision=obj['region_revision'])


def prepare(server,request,position):
 """Only authority-supplied adjacent actor/player coordinates determine force."""
 obj=request['target'];vector=[obj['x']-position[0],obj['y']-position[1]]
 if vector not in ([0,1],[0,-1],[1,0],[-1,0]):raise ValueError('Push requires exact adjacency')
 after=dict(obj,x=obj['x']+vector[0],y=obj['y']+vector[1])
 from .region_characters import validate_region_objects
 proposed=[after if o['id']==obj['id'] else o for o in server.objects]
 server._validated(dict(state=server.module_state,objects=proposed,tiles=[]))
 validate_region_objects(server,proposed,server.module_state)
 key=server.module_state.get('world_pushables',{}).get(obj['id'])
 if type(key) is not str or len(key)!=64:raise ValueError('Push definition unavailable')
 name='_push_vector_'+key[:16];source=server.candidate.source;tree=ast.parse(source)
 assignments=[n for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id==name]
 if len(assignments)!=1:raise ValueError('Push direction binding changed')
 node=assignments[0];old=ast.literal_eval(node.value)
 if old not in ([0,0],[0,1],[0,-1],[1,0],[-1,0]):raise ValueError('Push direction binding changed')
 lines=source.splitlines(keepends=True);lines[node.lineno-1:node.end_lineno]=[f'{name}={vector!r}\n']
 request['push_vector']=vector
 return ''.join(lines)
