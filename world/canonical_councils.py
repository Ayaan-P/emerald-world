"""Independent player answers, unanimous public cast decisions; no host override."""
import json
import re
from .guilds import GuildError


def validate(proposal):
    if proposal is None:return
    if (type(proposal) is not dict or set(proposal)-{'mode'}!={'question','options'}
            or proposal.get('mode','unanimous') not in ('unanimous','speaker')
            or type(proposal['question']) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,160}",proposal['question'])
            or type(proposal['options']) is not dict or not 2<=len(proposal['options'])<=3):
        raise ValueError('shared conversation needs a bounded question and two or three options')
    for key,label in proposal['options'].items():
        if (type(key) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,15}',key)
                or key=='withdraw' or type(label) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,48}",label)):
            raise ValueError('shared conversation options need bounded identifiers and labels')


def install(db):
    db.execute('''CREATE TABLE IF NOT EXISTS canonical_councils(
      guild_id INTEGER,actor TEXT,version INTEGER,roster TEXT,votes TEXT,seq INTEGER,
      PRIMARY KEY(guild_id,actor,version))''')
    # Membership edits invalidate pending consent even if someone leaves and
    # rejoins before the next council command. Completed history remains intact.
    db.executescript('''
      CREATE TRIGGER IF NOT EXISTS council_member_join AFTER INSERT ON guild_members
        BEGIN DELETE FROM canonical_councils WHERE guild_id=NEW.guild_id AND seq IS NULL; END;
      CREATE TRIGGER IF NOT EXISTS council_member_leave AFTER DELETE ON guild_members
        BEGIN DELETE FROM canonical_councils WHERE guild_id=OLD.guild_id AND seq IS NULL; END;
      CREATE TRIGGER IF NOT EXISTS council_member_change AFTER UPDATE ON guild_members
        BEGIN DELETE FROM canonical_councils WHERE guild_id IN (OLD.guild_id,NEW.guild_id) AND seq IS NULL; END;
    ''')


def command(server,conn,actor,row,args):
    from .canonical_cast import BINDINGS
    proposal=(row or {}).get('council')
    if not proposal:raise GuildError('No shared conversation question is currently offered.')
    if proposal.get('mode','unanimous')!='unanimous':raise GuildError('This is a speaker-led question. Use converse; listeners advise and the speaker chooses.')
    guild=server.guilds._require(conn['id'])
    members=server.guilds.members(conn['id'])[1]
    if not 2<=len(members)<=4:raise GuildError('Shared cast decisions support guilds of two to four trainers.')
    roster=json.dumps(sorted(members),separators=(',',':'))
    prior=server.db.execute('SELECT roster,votes,seq FROM canonical_councils WHERE guild_id=? AND actor=? AND version=?',(guild[0],actor,row['version'])).fetchone()
    if args==['council']:
        votes=json.loads(prior[1]) if prior and prior[0]==roster else {}
        return [proposal['question'],
            'Each trainer answers independently. Unanimous agreement publishes the choice and group size, never names or individual answers.',
            'No leader override. No agreement means no public outcome. This does not change anyone story progression.',
            'This version already concluded.' if prior and prior[2] else str(len(votes))+' of '+str(len(members))+' current members answered.',
            'Your answer: '+votes.get(conn['id'],'not answered')]+[
            key+': '+label for key,label in proposal['options'].items()]+[
            '/guild cast '+BINDINGS[actor]['wire']+' decide '+str(row['version'])+' CHOICE',
            'Use withdraw instead of CHOICE to remove your answer before agreement.']
    if len(args)!=3 or args[0]!='decide' or args[1]!=str(row['version']):
        raise GuildError('Question changed. Review council before answering its current version.')
    choice=args[2]
    if choice!='withdraw' and choice not in proposal['options']:raise GuildError('Choose one offered answer or withdraw.')
    if prior and prior[2]:return ['This question already concluded; no repeat outcome or reward.']
    # A changed guild roster invalidates every old answer, rather than allowing
    # replacements to inherit consent. Only current authenticated members vote.
    votes=json.loads(prior[1]) if prior and prior[0]==roster else {}
    if choice=='withdraw':votes.pop(conn['id'],None)
    else:votes[conn['id']]=choice
    seq=None
    with server.db:
        if len(votes)==len(members) and len(set(votes.values()))==1:
            choice=next(iter(votes.values()))
            seq=server.memory.append('canonical_council_agreed',dict(
                character_id=actor,character_version=row['version'],question=proposal['question'],
                choice=choice,label=proposal['options'][choice],participants=len(members),
                publication='explicit_unanimous_cast_choice',based_on=row['evidence'],
                places=['native:'+BINDINGS[actor]['map']],
                limits='Public group preference, not a completed activity, personal relationship or story-flag change.'))
        server.db.execute('INSERT OR REPLACE INTO canonical_councils VALUES(?,?,?,?,?,?)',
            (guild[0],actor,row['version'],roster,json.dumps(votes,sort_keys=True),seq))
        server.db.execute('DELETE FROM canonical_councils WHERE guild_id=? AND actor=? AND version<>? AND seq IS NULL',(guild[0],actor,row['version']))
    if seq:
        server.revision=seq
        return ['All current members agreed. The anonymous group preference is public; the character can consider it.']
    return ['Your answer was withdrawn.' if choice=='withdraw' else 'Your answer is recorded privately. No unanimous group preference yet.']


def relevant(event,actor):
    return (event.get('event')=='canonical_council_agreed' and event.get('character_id')==actor
            and event.get('publication')=='explicit_unanimous_cast_choice')
