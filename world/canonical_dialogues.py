"""Opt-in shared cast conversations: listeners advise, the speaker decides.

Only public authored material is shared. Never mirror a private native reply.
"""
import json
import secrets
import time
from .guilds import GuildError


def install(db):
    db.executescript('''
      CREATE TABLE IF NOT EXISTS canonical_dialogues(
        id TEXT PRIMARY KEY,guild_id INTEGER,actor TEXT,version INTEGER,speaker TEXT,
        proposal TEXT,members TEXT,advice TEXT,status TEXT,choice TEXT,seq INTEGER,expires REAL,
        UNIQUE(guild_id,actor,version));
      CREATE TRIGGER IF NOT EXISTS dialogue_member_leave AFTER DELETE ON guild_members
        BEGIN UPDATE canonical_dialogues SET status='cancelled'
          WHERE guild_id=OLD.guild_id AND status='open'; END;
      CREATE TRIGGER IF NOT EXISTS dialogue_member_change AFTER UPDATE ON guild_members
        BEGIN UPDATE canonical_dialogues SET status='cancelled'
          WHERE guild_id IN (OLD.guild_id,NEW.guild_id) AND status='open'; END;
    ''')


def read(server,identifier,guild,actor):
    row=server.db.execute('SELECT id,version,speaker,proposal,members,advice,status,choice,seq,expires FROM canonical_dialogues WHERE id=? AND guild_id=? AND actor=?',(identifier,guild,actor)).fetchone()
    if not row:raise GuildError('This shared conversation is unavailable to your guild.')
    return dict(zip(('id','version','speaker','proposal','members','advice','status','choice','seq','expires'),row))


def lines(session,trainer,current):
    proposal=json.loads(session['proposal']);members=json.loads(session['members']);advice=json.loads(session['advice'])
    counts={key:list(advice.values()).count(key) for key in proposal['options']}
    result=['Shared conversation '+session['id']+'; '+session['status']+'.',proposal['question'],
        'You are the speaker.' if trainer==session['speaker'] else 'You are an optional listener; your advice does not choose for the speaker.',
        str(len(members))+' participants. Only public authored dialogue is shared; private memories stay private.',
        'Speaker choice and anonymous advice counts may enter public world history. Names and private replies are not shared.']
    result.extend(key+': '+label+' ('+str(counts[key])+' suggestions)' for key,label in proposal['options'].items())
    if session['choice']:result.append('Speaker chose: '+proposal['options'][session['choice']]+'. This is not group consensus.')
    if session['status']=='chosen' and current and current['version']!=session['version']:
        result.extend(['The character has since reconsidered. Public response:',current['dialogue']])
    return result


def command(server,conn,actor,current,args):
    from .canonical_cast import BINDINGS,check_actor_location
    guild=server.guilds._require(conn['id'])[0];trainer=conn['id'];op=args[0]
    if op=='converse' and len(args)==1:
        proposal=(current or {}).get('council')
        if not proposal or proposal.get('mode','unanimous')!='speaker':raise GuildError('This actor has no speaker-led shared question.')
        if not (conn.get('state') or [0]*7)[6]:raise GuildError('Stand ready at the original actor to speak.')
        try:check_actor_location(server,conn,actor)
        except ValueError:raise GuildError('Visit the original actor before starting a conversation.') from None
        old=server.db.execute('SELECT id,status,expires FROM canonical_dialogues WHERE guild_id=? AND actor=? AND version=?',(guild,actor,current['version'])).fetchone()
        if old and (old[1]=='chosen' or old[1]=='open' and old[2]>time.time()):
            return ['A conversation already exists: '+old[0]+'. Use listen or conversation with that ID.']
        identifier=secrets.token_hex(4)
        with server.db:
            server.db.execute('INSERT OR REPLACE INTO canonical_dialogues VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (identifier,guild,actor,current['version'],trainer,json.dumps(proposal,sort_keys=True),json.dumps([trainer]),'{}','open',None,None,time.time()+300))
        return lines(read(server,identifier,guild,actor),trainer,current)+[
            'Listeners opt in with /guild cast '+BINDINGS[actor]['wire']+' listen '+identifier,
            'Advice: advise ID OPTION. Speaker: choose ID OPTION. Choice publishes an anonymous speaker decision, never group consensus.',
            'Use conversation ID to review or leave ID to exit. Session lasts five minutes.']
    if len(args) not in (2,3):raise GuildError('Use converse, listen ID, conversation ID, advise ID OPTION, choose ID OPTION or leave ID.')
    session=read(server,args[1],guild,actor)
    members=json.loads(session['members']);advice=json.loads(session['advice']);proposal=json.loads(session['proposal'])
    if session['status']=='open' and (time.time()>session['expires'] or not current or current['version']!=session['version']):
        with server.db:server.db.execute("UPDATE canonical_dialogues SET status='expired' WHERE id=?",(session['id'],))
        session['status']='expired'
    if op=='conversation' and len(args)==2:
        if trainer not in members:raise GuildError('Opt in with listen before reviewing this conversation.')
        return lines(session,trainer,current)
    if op=='leave' and len(args)==2:
        if trainer not in members:return ['You are not listening to this conversation.']
        members.remove(trainer);advice.pop(trainer,None)
        status='cancelled' if trainer==session['speaker'] and session['status']=='open' else session['status']
        with server.db:server.db.execute('UPDATE canonical_dialogues SET members=?,advice=?,status=? WHERE id=?',(json.dumps(members),json.dumps(advice),status,session['id']))
        return ['You left the conversation. Existing public decisions remain unchanged.']
    if session['status']!='open':raise GuildError('This conversation is no longer open.')
    if not (conn.get('state') or [0]*7)[6]:raise GuildError('Stand ready at the original actor to participate.')
    try:check_actor_location(server,conn,actor)
    except ValueError:raise GuildError('Visit the original actor before joining or answering.') from None
    if op=='listen' and len(args)==2:
        if trainer not in members:
            if len(members)>=4:raise GuildError('This conversation already has four participants.')
            members.append(trainer)
            with server.db:server.db.execute('UPDATE canonical_dialogues SET members=? WHERE id=?',(json.dumps(members),session['id']))
        session['members']=json.dumps(members)
        return lines(session,trainer,current)
    if trainer not in members:raise GuildError('Opt in with listen before offering advice.')
    if len(args)!=3 or args[2] not in proposal['options']:raise GuildError('Choose an offered answer.')
    choice=args[2]
    if op=='advise':
        if trainer==session['speaker']:raise GuildError('As speaker, use choose; others may offer advice.')
        advice[trainer]=choice
        with server.db:server.db.execute('UPDATE canonical_dialogues SET advice=? WHERE id=?',(json.dumps(advice,sort_keys=True),session['id']))
        return ['Advice shared with the conversation. The speaker still decides; you can leave to remove pending advice.']
    if op!='choose' or trainer!=session['speaker']:raise GuildError('Only the conversation speaker can choose; listeners advise.')
    with server.db:
        seq=server.memory.append('canonical_speaker_decided',dict(
            character_id=actor,character_version=session['version'],question=proposal['question'],choice=choice,label=proposal['options'][choice],
            participants=len(members),advice={key:list(advice.values()).count(key) for key in proposal['options']},
            publication='explicit_speaker_choice_with_optional_advice',based_on=current['evidence'],places=['native:'+BINDINGS[actor]['map']],
            limits='Speaker choice, not unanimity, participant agreement, personal relationship, completed activity or story progression.'))
        server.db.execute("UPDATE canonical_dialogues SET status='chosen',choice=?,seq=? WHERE id=?",(choice,seq,session['id']))
    server.revision=seq
    return ['The speaker choice is public, with anonymous advice counts. It is not group consensus. The character can consider it.']


def relevant(event,actor):
    return (event.get('event')=='canonical_speaker_decided' and event.get('character_id')==actor
            and event.get('publication')=='explicit_speaker_choice_with_optional_advice')
