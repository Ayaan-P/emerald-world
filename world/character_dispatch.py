"""Bounded current character command; append-only causal archive at admission."""
import ast,copy,hashlib,inspect,json

def source(old,actions,definition,state):
 from .character_actions import action_step
 helper=inspect.getsource(action_step).replace('def action_step(','def _ew_character_dispatch_v1(',1)
 helper=helper.replace("receipts=state.setdefault('world_character_action_receipts',[])","receipts=state.setdefault('world_character_current_receipt',{})")
 helper=helper.replace("        if len(receipts)>=32:raise ValueError('character action receipt limit')","        receipts.clear()")
 helper=helper.replace('        receipts.append(definition)','        receipts[definition]=copy.deepcopy(actions)')
 wrapper="def update(context,state):\n    if not state:\n        import copy\n        state=copy.deepcopy(_ew_character_seed_v1)\n    return _ew_character_dispatch_v1(_ew_character_request_v1[0],_ew_character_request_v1[1],_ew_character_previous_v1(context,state),context)\n"
 tree=ast.parse(old);request=(actions,definition)
 assigns=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_ew_character_request_v1' for t in n.targets)]
 if assigns:
  funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
  old_helper=helper.replace("controls.get(identity,{}).get('object',visible.get(identity))!=condition['source']", "visible.get(identity)!=condition['source']")
  migration=[n for n in funcs if ast.dump(n,include_attributes=False)==ast.dump(ast.parse(old_helper).body[0],include_attributes=False)]
  seeds=[n for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='_ew_character_seed_v1']
  if (len(assigns)!=1 or len(assigns[0].targets)!=1 or len(seeds)!=1 or
      not (migration or any(ast.dump(n,include_attributes=False)==ast.dump(ast.parse(helper).body[0],include_attributes=False) for n in funcs)) or
      not any(ast.dump(n,include_attributes=False)==ast.dump(ast.parse(wrapper).body[0],include_attributes=False) for n in funcs)):
   raise ValueError('Reusable character dispatcher changed; explicit source consolidation required')
  lines=old.splitlines(keepends=True)
  edits=[(assigns[0],request),(seeds[0],state)]
  if migration and old_helper!=helper:edits.append((migration[0],None))
  for node,value in sorted(edits,key=lambda pair:pair[0].lineno,reverse=True):
   if isinstance(node,ast.FunctionDef):lines[node.lineno-1:node.end_lineno]=[helper]
   else:
    ast.literal_eval(node.value)
    lines[node.lineno-1:node.end_lineno]=[f'{node.targets[0].id}={value!r}\n']
  return ''.join(lines)
 if any(isinstance(n,ast.Name) and n.id.startswith('_ew_character_') for n in ast.walk(tree)):raise ValueError('Reserved character dispatcher names already used')
 return old+f'\n_ew_character_previous_v1=update\n_ew_character_seed_v1={state!r}\n_ew_character_request_v1={request!r}\n'+helper+'\n'+wrapper

def admitted(server,definition):
 if definition in server.module_state.get('world_character_current_receipt',{}) or definition in server.module_state.get('world_character_action_receipts',[]):return True
 if not server.db.execute("SELECT 1 FROM sqlite_master WHERE name='character_action_archive'").fetchone():return False
 return bool(server.db.execute('SELECT 1 FROM character_action_archive WHERE id=?',(definition,)).fetchone())

def archive(server,before,state,objects):
 if 'world_character_current_receipt' not in state:return # A separately authored source may replace the dispatcher; archive is retained.
 current=state.get('world_character_current_receipt',{})
 if current==before.get('world_character_current_receipt',{}):return
 if type(current) is not dict or len(current)!=1:raise ValueError('One current character action receipt required')
 definition,actions=next(iter(current.items()))
 if type(actions) is not list or not 1<=len(actions)<=8 or hashlib.sha256(json.dumps(actions,sort_keys=True).encode()).hexdigest()!=definition:
  raise ValueError('Invalid character command receipt')
 changes=[]
 for action in actions:
  actor=action['id'];old=before.get('world_characters',{}).get(actor);new=state.get('world_characters',{}).get(actor)
  if not old or not new or old['version']!=action['expected_version'] or new['version']!=old['version']+1:
   raise ValueError('Character receipt does not match admitted version')
  expected=copy.deepcopy(old);expected.update(copy.deepcopy(action['changes']),version=old['version']+1,evidence=action['evidence'],reason=action['reason'])
  if expected.get('offer') is None:expected.pop('offer',None)
  if new!=expected:raise ValueError('Character command differs from admitted character')
  expected_object=copy.deepcopy(action['object'])
  if 'walk' in action or 'journey' in action:
   expected_object['x'],expected_object['y']=action.get('journey',action.get('walk'))[0]
  control=state.get('world_character_controls',{}).get(actor,{})
  obj=next((o for o in objects if o['id']==actor),None)
  if obj!=expected_object or control.get('character')!=new or control.get('object')!=obj:raise ValueError('Character receipt lacks exact admitted control')
  changes.append(dict(actor=actor,before=old,after=new,object_before=next((o for o in server.objects if o['id']==actor),None),object_after=obj))
 server.db.execute('CREATE TABLE IF NOT EXISTS character_action_archive(id TEXT PRIMARY KEY,data TEXT,seq INTEGER)')
 if server.db.execute('SELECT 1 FROM character_action_archive WHERE id=?',(definition,)).fetchone():raise ValueError('Character action identity already committed')
 data=dict(request=definition,actions=actions,changes=changes,source='validated_mechanic_admission')
 seq=server.memory.append('character_action_committed',data)
 server.db.execute('INSERT INTO character_action_archive VALUES(?,?,?)',(definition,json.dumps(data,sort_keys=True),seq));server.revision=seq
