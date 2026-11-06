"""Guild commands over the existing player chat and field interfaces.

Kept separate from the engine and transport so either game client can use the
same world authority. All input has already passed native chat validation.
"""
import time
from .guilds import GuildError

class GuildChat:
    def __init__(self, server, validate_coords, freshness):
        self.server=server
        self.validate_coords=validate_coords
        self.freshness=freshness
        self.epoch=0

    def message(self, recipient, sender, text):
        s=self.server
        if not 1<=len(text)<=120 or not text.isascii(): raise ValueError('invalid guild response')
        s.chat_serial += 1
        message=(s.chat_serial,sender,recipient['id'],text.encode('ascii').hex())
        recipient['chat_history']=(recipient['chat_history']+[message])[-16:]

    def online(self, trainer, args):
        s=self.server
        if len(args)>1 or (args and (not args[0].isascii() or not args[0].isdecimal() or len(args[0])>2)):
            raise GuildError('Use /guild online or /guild online PAGE.')
        page=int(args[0]) if args else 1
        if page<1: raise GuildError('Page must start at 1.')
        _,members=s.guilds.members(trainer);online=[]
        for name in members:
            peer=s.peers.get(name)
            if not peer or peer.get('closing'): continue
            state=peer.get('state');location='not in the field'
            fresh=peer.get('state_time') is not None and time.monotonic()-peer['state_time']<=self.freshness
            if state and fresh and (state[6] or peer.get('field')):
                if tuple(state[:2]) in (s.cave_map,s.wilds_map): location='generated area'
                else:
                    try: location=self.validate_coords(*state[:4])['name']
                    except ValueError: location='unknown area'
                if not state[6]: location+=' (busy)'
            online.append(f'{name}: {location}')
        pages=max(1,(len(online)+7)//8)
        if page>pages: raise GuildError(f'Page must be 1-{pages}.')
        return [f'Guild online {page}/{pages}:']+(online[(page-1)*8:page*8] or ['No guild members online.'])

    def handle(self, conn, text):
        """Consume guild commands, return False for ordinary public chat."""
        s=self.server
        if text == '/guild' or text.startswith('/guild '):
            with s.lock:
                try:
                    command=text[6:].strip();words=command.split()
                    if words and words[0].lower()=='online': lines=self.online(conn['id'],words[1:])
                    else:
                        if (len(words)==4 and words[0].lower()=='expedition'
                                and words[1].lower()=='start' and words[2].lower()=='here'):
                            state=conn.get('state')
                            fresh=conn.get('state_time') is not None and time.monotonic()-conn['state_time']<=self.freshness
                            if not state or not fresh or not state[6] or tuple(state[:2]) in (s.cave_map,s.wilds_map):
                                raise GuildError('Stand ready on a standard map before starting here.')
                            command=f'expedition start {self.validate_coords(*state[:4])["name"]} {words[3]}'
                        lines=s.guilds.command(conn['id'],command)
                        self.epoch+=1
                except GuildError as exc: lines=[str(exc)]
                for line in lines: self.message(conn,conn['id'],'Guild: '+line)
                parts=text.split()
                if len(parts)==3 and parts[1].lower()=='invite' and lines[0].startswith('Invited '):
                    invitee=s.peers.get(parts[2]);guild=s.guilds._member(conn['id'])
                    if invitee and invitee.get('chat') and not invitee.get('closing') and guild:
                        self.message(invitee,conn['id'],f'Guild: {conn["id"]} invited you to {guild[1]}. Use /guild accept {guild[1]}')
                        s._queue(invitee,s._snapshot(invitee))
                if len(parts)==3 and parts[1].lower()=='apply' and lines[0].startswith('Applied to '):
                    row=s.guilds.db.execute('SELECT name,leader FROM guilds WHERE name=? COLLATE NOCASE',(parts[2],)).fetchone()
                    leader=s.peers.get(row[1]) if row else None
                    if leader and leader.get('chat') and not leader.get('closing'):
                        self.message(leader,conn['id'],f'Guild: {conn["id"]} applied to {row[0]}. Use /guild applications')
                        s._queue(leader,s._snapshot(leader))
                if len(parts)==3 and parts[1].lower()=='approve' and lines[0].startswith('Approved '):
                    applicant=s.peers.get(parts[2]);guild=s.guilds._member(conn['id'])
                    if applicant and applicant.get('chat') and not applicant.get('closing') and guild:
                        self.message(applicant,conn['id'],f'Guild: Your application was accepted. You joined {guild[1]}.')
                        s._queue(applicant,s._snapshot(applicant))
                if len(parts)>=3 and parts[1].lower()=='post' and lines[0]=='Posted to the guild board.':
                    _,members=s.guilds.members(conn['id'])
                    for name in members:
                        if name==conn['id']: continue
                        recipient=s.peers.get(name)
                        if recipient and recipient.get('chat') and not recipient.get('closing'):
                            self.message(recipient,conn['id'],f'Guild board: {conn["id"]} posted. Use /guild board')
                            s._queue(recipient,s._snapshot(recipient))
            conn['chat_status']='sent';s._queue(conn,s._snapshot(conn));return True
        if text=='/g' or text.startswith('/g '):
            with s.lock:
                try:
                    _,members=s.guilds.members(conn['id']);body=text[3:].strip()
                    if not body or len(body)>112: raise GuildError('Use /g followed by 1-112 characters.')
                    for name in members:
                        recipient=s.peers.get(name)
                        if recipient and recipient.get('chat') and not recipient.get('closing'):
                            self.message(recipient,conn['id'],'[Guild] '+body)
                            s._queue(recipient,s._snapshot(recipient))
                except GuildError as exc:
                    self.message(conn,conn['id'],'Guild: '+str(exc));s._queue(conn,s._snapshot(conn))
            conn['chat_status']='sent';s._queue(conn,s._snapshot(conn));return True
        return False

    def observe(self, conn, state):
        """Advance expeditions from authenticated, validated ready field states."""
        s=self.server
        if not state[6] or tuple(state[:2]) in (s.cave_map,s.wilds_map): return
        key=(self.epoch,state[0],state[1])
        if conn.get('guild_visit_key')==key: return
        conn['guild_visit_key']=key
        completed=s.guilds.visit(conn['id'],self.validate_coords(*state[:4])['name'])
        if not completed: return
        _,destination,goal,members=completed
        notice=f'Guild expedition complete: {destination} ({goal} trainers).'
        for name in members:
            recipient=s.peers.get(name)
            if recipient and recipient.get('chat') and not recipient.get('closing'):
                self.message(recipient,conn['id'],notice);s._queue(recipient,s._snapshot(recipient))
