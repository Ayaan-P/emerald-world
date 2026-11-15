"""Public authored questions; answers and player outcomes never leave the game."""
import json,re,time
from .build_catalog import catalog_maps
TEXT=re.compile(r"[A-Za-z0-9 .,?!'-]+\Z")
def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS trick_questions(id INTEGER PRIMARY KEY CHECK(id=1),actor TEXT,revision INTEGER,body TEXT)')
def text(value,limit):
 if not isinstance(value,str) or not 1<=len(value)<=limit or value.strip()!=value or not TEXT.fullmatch(value) or any(len(w)>18 for w in value.split()):raise ValueError('Use bounded plain English text without controls')
 return value

def catalog(server):
 setup(server.db)
 row=server.db.execute('SELECT actor,revision,body FROM trick_questions WHERE id=1').fetchone()
 return dict(pack=None if not row else dict(actor=row[0],revision=row[1],**json.loads(row[2])),limits='Five authored quiz gates in the existing fifth Trick House room. Optional personal choice, original movement/failure/rewards. No answer sharing, earned-history claims or new postgame replay. Authored answers may be wrong; the player can retain stock questions.')

def configure(server,actor,row,args):
 setup(server.db)
 if set(args)!={'expected_revision','title','questions','active'}:raise ValueError('Supply complete question pack')
 if type(args['expected_revision']) is not int or not 0<=args['expected_revision']<4294967295 or type(args['active']) is not bool:raise ValueError('Invalid revision or active')
 title=text(args['title'],24);questions=args['questions']
 if not isinstance(questions,list) or len(questions)!=5:raise ValueError('Exactly five questions')
 for q in questions:
  if not isinstance(q,dict) or set(q)!={'question','choices','answer'}:raise ValueError('Invalid question')
  text(q['question'],96)
  if not isinstance(q['choices'],list) or len(q['choices'])!=3 or len(set(q['choices']))!=3:raise ValueError('Three distinct choices')
  for c in q['choices']:text(c,18)
  if type(q['answer']) is not int or not 0<=q['answer']<3:raise ValueError('Answer index 0..2')
 old=server.db.execute('SELECT actor,revision FROM trick_questions WHERE id=1').fetchone()
 if (old and old[0]!=actor) or (old[1] if old else 0)!=args['expected_revision']:raise ValueError('Pack ownership/revision changed')
 revision=(old[1] if old else 0)+1
 body=dict(schema=1,title=title,questions=questions,active=args['active'])
 server.db.execute('INSERT OR REPLACE INTO trick_questions VALUES(1,?,?,?)',(actor,revision,json.dumps(body)))
 seq=server.memory.append('trick_question_pack_authored',dict(character_id=actor,revision=revision,**body,basis='authored_quiz_not_verified_fact_or_player_result'))
 server.revision=seq
 return dict(outcome='published',revision=revision)

def wire(server,conn,raw):
 setup(server.db)
 try:
  w=raw.decode('ascii').split()
  if len(w)!=3 or w[:2]!=['TQ','GET'] or not w[2].isdigit() or not 0<int(w[2])<2**32:return 'TQ NONE 0\n'
  nonce=w[2];p=conn['presence'];state=p.get('state')
  if not state or time.monotonic()-p.get('state_time',0)>5 or catalog_maps().get(tuple(state[:2]),{}).get('name')!='Route110_TrickHousePuzzle5':return f'TQ NONE {nonce}\n'
  if time.monotonic()<conn.get('trick_next_get',0):return f'TQ NONE {nonce}\n'
  conn['trick_next_get']=time.monotonic()+3
  row=server.db.execute('SELECT revision,body FROM trick_questions WHERE id=1').fetchone()
  if not row:return f'TQ NONE {nonce}\n'
  revision,body=row[0],json.loads(row[1])
  if body.get('schema')!=1 or not body.get('active'):return f'TQ NONE {nonce}\n'
  hx=lambda s:s.encode('ascii').hex()
  lines=[f"TQ BEGIN {nonce} {revision} {hx(body['title'])}\n"]
  for i,q in enumerate(body['questions']):lines.append(f"TQ ROW {nonce} {revision} {i} {q['answer']} {hx(q['question'])} "+' '.join(hx(c) for c in q['choices'])+'\n')
  lines.append(f'TQ END {nonce} {revision}\n')
  return ''.join(lines)
 except (UnicodeError,ValueError,KeyError,TypeError):return 'TQ NONE 0\n'
