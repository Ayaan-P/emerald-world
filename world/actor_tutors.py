"""Optional native move-tutor opportunities; no party edits or learned claims."""
MOVES={38:'Double-Edge',102:'Mimic',118:'Metronome',153:'Explosion',164:'Substitute',
       205:'Rollout',207:'Swagger',210:'Fury Cutter',214:'Sleep Talk',223:'Dynamic Punch'}
def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS actor_tutors(actor TEXT PRIMARY KEY,revision INTEGER,move INTEGER)')
def configure(server,actor,row,args):
 from .characters import records
 if set(args)!={'move'} or type(args['move']) is not int or args['move'] not in (0,*MOVES):raise ValueError('Choose a reviewed existing tutor move; 0 closes the opportunity')
 current=records(server.module_state).get(actor)
 if not current or current['status']!='active':raise ValueError('Active world-owned tutor required')
 seq=server.memory.append('character_tutoring_changed',dict(character_id=actor,move=args['move'],basis='authority_tutor_opportunity',
  limits='Optional repeatable free native tutoring. Player chooses Pokemon/replacement; engine checks eligibility. No teaching, mastery or relationship inferred.'))
 server.db.execute('INSERT INTO actor_tutors VALUES(?,?,?) ON CONFLICT(actor) DO UPDATE SET revision=excluded.revision,move=excluded.move',(actor,seq,args['move']))
 server.revision=seq
 return dict(outcome='tutoring_offered' if args['move'] else 'tutoring_closed',revision=seq,move=args['move'])
def line(server,conn,actor,version):
 if not conn.get('character_tutor_capable'):return None
 saved=server.db.execute('SELECT revision,move FROM actor_tutors WHERE actor=?',(actor,)).fetchone()
 if not saved or not saved[1]:return None
 return 'CHARACTER_TUTOR '+' '.join(map(str,[actor,version,*saved]))
def catalog(server):
 return dict(moves={str(k):v for k,v in MOVES.items()},offers={a:dict(revision=r,move=m) for a,r,m in server.db.execute('SELECT actor,revision,move FROM actor_tutors')},
  semantics='Player-selected repeatable free native tutoring, not an authored party edit or proof of learned moves. Canonical tutors and once-only flags remain unchanged.')
