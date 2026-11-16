"""Composable native strategy preferences for optional generated-trainer battles."""
import json
from .characters import records
FLAGS={'setup_first':3,'risky':4,'seek_two_hit_ko':5,'baton_pass':6,'hp_aware':8,'field_status':9,'prefer_status':12,'reserve_ace':15}
def setup(db):db.execute('CREATE TABLE IF NOT EXISTS npc_tactics(actor TEXT PRIMARY KEY,flags TEXT,revision INTEGER)')
def configure(server,actor,row,args):
 setup(server.db)
 if set(args)!={'flags'} or type(args['flags']) is not str:raise ValueError('Supply JSON list of supported native strategy flags')
 try:flags=json.loads(args['flags'])
 except ValueError:raise ValueError('Invalid flags JSON') from None
 if type(flags)is not list or len(flags)>len(FLAGS) or any(type(f)is not str or f not in FLAGS for f in flags) or len(set(flags))!=len(flags):raise ValueError('Use distinct discovered strategy flags, or [] for normal AI')
 c=records(server.module_state).get(actor)
 if not c or c['status']!='active':raise ValueError('Active generated trainer required')
 flags=sorted(flags)
 seq=server.memory.append('npc_tactics_configured',dict(character_id=actor,flags=flags,basis='native_optional_trainer_ai_configuration',limits='Preferences for a future optional battle, not moves taken, growth or victory. No omniscience, new moves, stats, items or player party edits.'))
 server.db.execute('INSERT INTO npc_tactics VALUES(?,?,?) ON CONFLICT(actor) DO UPDATE SET flags=excluded.flags,revision=excluded.revision',(actor,json.dumps(flags),seq));server.revision=seq
 return dict(outcome='native_tactics_configured',flags=flags,revision=seq)
def catalog(server):
 setup(server.db);cast=records(server.module_state)
 return [dict(actor=a,version=cast[a]['version'],flags=json.loads(f),revision=r) for a,f,r in server.db.execute('SELECT actor,flags,revision FROM npc_tactics ORDER BY actor') if a in cast and cast[a]['status']=='active']
def wire(server,conn,raw):
 if raw!=b'A GET 1':return 'A ERROR SHAPE\n'
 entries=catalog(server)
 return 'A BEGIN 1 '+str(len(entries))+'\n'+''.join(f"A ENTRY {e['actor']} {e['version']} {sum(1<<FLAGS[f] for f in e['flags'])}\n" for e in entries)+'A END 1\n'
def command(server,conn,words):
 from .guilds import GuildError
 if len(words)>1:raise GuildError('Use /guild tactics [ACTOR]')
 entries=catalog(server)
 if words:entries=[e for e in entries if e['actor']==words[0]]
 return ['Optional generated trainer tactics (native AI preferences, not guaranteed moves):']+[e['actor']+': '+(', '.join(e['flags']) or 'normal') for e in entries[:12]]+['Existing moves/party only. Canonical and co-op battles unchanged.']
