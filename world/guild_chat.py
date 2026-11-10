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
                    if words and words[0].lower()=='pyramid':
                        from .pyramid_courses import command as pyramid_command
                        lines=pyramid_command(s,conn,words[1:])
                    elif words and words[0].lower()=='tower':
                        from .tower_exchange import command as tower_command
                        lines=tower_command(s,conn,words[1:])
                    elif words and words[0].lower()=='starters':
                        from .starter_offers import command as starter_command
                        lines=starter_command(s,conn,words[1:])
                    elif words and words[0].lower()=='mazes':
                        from .maze_courses import command as maze_command
                        lines=maze_command(s,conn,words[1:])
                    elif words and words[0].lower()=='bases':
                        from .base_neighborhood import command as base_directory_command
                        lines=base_directory_command(s,conn,words[1:])
                    elif words and words[0].lower()=='tournament':
                        from .player_tournaments import command as tournament_command
                        lines=tournament_command(s,conn,words[1:])
                    elif words and words[0].lower()=='rematches':
                        from .route_rematch_events import command as rematch_command
                        lines=rematch_command(s,conn,words[1:])
                    elif words and words[0].lower()=='research':
                        from .shared_research import command as research_command
                        lines=research_command(s,conn,words[1:])
                    elif words and words[0].lower()=='tactics':
                        from .npc_tactics import command as tactics_command
                        lines=tactics_command(s,conn,words[1:])
                    elif words and words[0].lower()=='chart':
                        from .shared_cartography import command as chart_command
                        lines=chart_command(s,conn,words[1:])
                    elif words and words[0].lower()=='npc':
                        from .npc_conversations import command as npc_command
                        lines=npc_command(s,conn,words[1:])
                    elif words and words[0].lower()=='safari':
                        from .safari_outings import command as safari_command
                        lines=safari_command(s,conn,words[1:])
                    elif words and words[0].lower()=='cargo':
                        from .player_cargo import command as cargo_command
                        lines=cargo_command(s,conn,words[1:])
                    elif words and words[0].lower()=='reconstruction':
                        from .reconstruction import command as reconstruction_command
                        lines=reconstruction_command(s,conn,words[1:])
                    elif words and words[0].lower()=='object':
                        from .object_choices import command as object_command
                        lines=object_command(s,conn,words[1:])
                    elif words and words[0].lower()=='contests':
                        from .contest_guests import command as contest_command
                        lines=contest_command(s,conn,words[1:])
                    elif words and words[0].lower()=='fishing':
                        from .shared_fishing import command as fishing_command
                        lines=fishing_command(s,conn,words[1:])
                    elif words and words[0].lower()=='outbreaks':
                        from .shared_outbreaks import command as outbreak_command
                        lines=outbreak_command(s,conn,words[1:])
                    elif words and words[0].lower()=='campaign':
                        from .battle_campaigns import command as campaign_command
                        lines=campaign_command(s,conn,words[1:])
                    elif words and words[0].lower()=='cast':
                        from .canonical_cast import guild_command
                        lines=guild_command(s,conn,words[1:])
                        self.epoch+=1
                    elif words and words[0].lower()=='play' and getattr(s, 'activities', None):
                        lines=[line[:113] for line in s.activities.command(conn,words[1:])]
                    elif words and words[0].lower()=='race' and getattr(s, 'races', None):
                        lines=s.races.command(conn,words[1:])
                    elif words and words[0].lower()=='flag' and getattr(s, 'flags', None):
                        lines=s.flags.command(conn,words[1:])
                    elif words and words[0].lower()=='relay' and getattr(s, 'relays', None):
                        lines=s.relays.command(conn,words[1:])
                    elif words and words[0].lower()=='online': lines=self.online(conn['id'],words[1:])
                    else:
                        generated=None
                        if (len(words)==4 and words[0].lower() in ('expedition','meet')
                                and words[1].lower()=='start' and words[2].lower()=='here'):
                            state=conn.get('state')
                            fresh=conn.get('state_time') is not None and time.monotonic()-conn['state_time']<=self.freshness
                            if not state or not fresh or not state[6]:
                                raise GuildError('Stand ready in the destination before starting here.')
                            if tuple(state[:2]) in (s.cave_map,s.wilds_map):
                                from .generated_goals import observed_place
                                generated=observed_place(s,conn,self.freshness)
                                if words[0].lower()!='expedition' or generated is None:
                                    raise GuildError('Only expeditions in admitted immutable places are supported here.')
                            else:command=f'{words[0].lower()} start {self.validate_coords(*state[:4])["name"]} {words[3]}'
                        lines=(s.guilds.expedition(conn['id'],['start','here',words[3]],place=generated) if generated else s.guilds.command(conn['id'],command))
                        self.epoch+=1
                except GuildError as exc: lines=[str(exc)]
                if not words:lines.append('Original character field proposals: /guild cast ACTOR')
                if not words:
                    lines.append('Talk publicly to nearby recurring NPCs: /guild npc')
                    lines.append('Choose shared object actions while facing one: /guild object choices')
                if not words and getattr(s, 'relays', None):lines.append('Find games and partners: /guild play')
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
                            if recipient is not conn: s._queue(recipient,s._snapshot(recipient))
                except GuildError as exc:
                    self.message(conn,conn['id'],'Guild: '+str(exc))
            conn['chat_status']='sent';s._queue(conn,s._snapshot(conn));return True
        return False

    def observe(self, conn, state):
        """Advance expeditions from authenticated, validated ready field states."""
        s=self.server
        if not state[6]:
            conn.pop('guild_visit_key',None)
            conn.pop('guild_last_ready_time',None)
            return
        generated=None
        if tuple(state[:2]) in (s.cave_map,s.wilds_map):
            from .generated_goals import observed_place
            generated=observed_place(s,conn,self.freshness)
            if generated is None:
                conn.pop('guild_visit_key',None);return
        now=time.monotonic();last=conn.get('guild_last_ready_time')
        conn['guild_last_ready_time']=now
        key=(self.epoch,state[0],state[1],generated['revision'] if generated else None)
        if conn.get('guild_visit_key')==key and last is not None and now-last<=self.freshness: return
        conn['guild_visit_key']=key
        map_name=generated['label'] if generated else self.validate_coords(*state[:4])['name']
        try:
            completed=s.guilds.visit(conn['id'],map_name,place=generated) if generated else s.guilds.visit(conn['id'],map_name)
        except GuildError as exc:
            self._outcome_error(conn,exc)
            return
        if completed:
            _,destination,goal,members=completed
            self._announce(conn,members,f'Guild expedition complete: {destination} ({goal} trainers). +10 guild XP.')
        if generated:return
        if s.guilds.active_meet(conn['id'],map_name):
            now=time.monotonic();ready=[]
            for name,peer in s.peers.items():
                other=peer.get('state');observed=peer.get('state_time')
                if (not peer.get('closing') and other and other[6] and observed is not None
                        and now-observed<=self.freshness and other[:2]==state[:2]):
                    ready.append(name)
            try:
                completed=s.guilds.complete_meet(conn['id'],map_name,ready)
            except GuildError as exc:
                self._outcome_error(conn,exc)
                return
            if completed:
                _,destination,goal,members=completed
                self._announce(conn,members,f'Guild meetup complete: {goal} trainers together at {destination}. +15 guild XP.')

    def _outcome_error(self, conn, error):
        # The completion transaction rolled back. Do not suppress the next
        # otherwise-identical valid presence report as an already-counted visit.
        conn.pop('guild_visit_key',None)
        if conn.get('chat'):
            self.message(conn,conn['id'],'Guild: '+str(error))
            self.server._queue(conn,self.server._snapshot(conn))

    def _announce(self, conn, members, text):
        s=self.server
        if getattr(s,'memory',None) is not None:
            s.revision=s.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
        for name in members:
            recipient=s.peers.get(name)
            if recipient and recipient.get('chat') and not recipient.get('closing'):
                self.message(recipient,conn['id'],text);s._queue(recipient,s._snapshot(recipient))
