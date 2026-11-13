"""Immutable retired identities outside the bounded live simulation state."""
import copy,json,re
KEY='world_character_archive_refs'

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS historical_characters(id TEXT PRIMARY KEY,record TEXT NOT NULL,archived_seq INTEGER NOT NULL)')

def refs(state,archived):
 cast=state.get('world_characters',{}); result={}
 for row in cast.values():
  for target in row.get('relationships',{}):
   if target not in cast and target in archived:
    old=archived[target];result[target]=dict(name=old['name'],version=old['version'])
 if result:state[KEY]=result
 else:state.pop(KEY,None)

def project(server,result):
 """Normalize exact replay only. Never silently discard a changed archived actor."""
 setup(server.db)
 names={o.get('id') for o in result.get('objects',[])}
 for state in (server.module_state,result['state']):
  for identity, row in state.get('world_characters',{}).items():
   names.add(identity);names.update(row.get('relationships',{}))
 archived={}
 names=sorted(n for n in names if type(n) is str)
 for offset in range(0,len(names),400):
  batch=names[offset:offset+400]
  for identity,raw in server.db.execute('SELECT id,record FROM historical_characters WHERE id IN ('+','.join('?' for _ in batch)+')',batch):archived[identity]=json.loads(raw)
 pending={i:copy.deepcopy(c) for i,c in server.module_state.get('world_characters',{}).items() if c.get('status')=='retired' and i not in archived}
 archived.update(pending)
 result=copy.deepcopy(result);before=copy.deepcopy(server.module_state)
 for state in (before,result['state']):
  cast=state.get('world_characters',{})
  for identity in set(cast)&archived.keys():
   if cast[identity]!=archived[identity]:raise ValueError('Archived character identity cannot be changed or reused')
   del cast[identity]
  refs(state,archived)
 if any(o.get('id') in archived for o in result.get('objects',[])):raise ValueError('Archived characters cannot render or resume activity')
 return result,before,pending

def commit(server,pending):
 # Called inside the same transaction as the admitted mechanic/module state.
 for identity,row in pending.items():
  seq=server.memory.append('character_archived',dict(character_id=identity,name=row['name'],version=row['version'],
      publication='public_retired_character_archive',basis='previously_committed_explicit_retirement',
      limits='Archived simulation record, not death or deletion. Original history and individual roster retained.'))
  server.db.execute('INSERT INTO historical_characters VALUES(?,?,?)',(identity,json.dumps(row,sort_keys=True),seq))
  server.revision=seq

def recall(server,actor,row,args):
 setup(server.db)
 if set(args)!={'after','identity'} or type(args['after']) is not str or type(args['identity']) is not str:raise ValueError('Use identity or after cursor')
 for value in args.values():
  if value and not re.fullmatch('[A-Za-z0-9_-]{1,24}',value):raise ValueError('Invalid archived identity')
 if args['identity']:
  saved=server.db.execute('SELECT record,archived_seq FROM historical_characters WHERE id=?',(args['identity'],)).fetchone()
  if not saved:raise ValueError('Archived character unavailable')
  return dict(outcome='archived_character_recalled',identity=args['identity'],record=json.loads(saved[0]),archived_seq=saved[1],
      limits='Public authored final record, not a present actor, witnessed event or verified battle. Original events remain in public history.')
 rows=server.db.execute('SELECT id,record,archived_seq FROM historical_characters WHERE id>? ORDER BY id LIMIT 9',(args['after'],)).fetchall()
 return dict(outcome='archived_characters_page',characters=[dict(id=i,name=json.loads(raw)['name'],version=json.loads(raw)['version'],archived_seq=seq) for i,raw,seq in rows[:8]],
     after=rows[7][0] if len(rows)>8 else (rows[-1][0] if rows else args['after']),has_more=len(rows)>8)
