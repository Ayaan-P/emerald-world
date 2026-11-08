"""Persistent player guilds, independent of game-engine and save layouts.

Only authenticated world identities can be supplied by the server. Calls run
under the world's lock. This module never reads or changes trainer saves.
"""
import re

NAME = re.compile(r'[A-Za-z0-9_-]{1,24}\Z')
MAX_MEMBERS = 50

class GuildError(ValueError):
    pass

class Guilds:
    def __init__(self, db, catalog=None):
        self.db = db
        self.maps = {m['name'].lower(): m['name'] for m in (catalog or {}).values()}
        db.executescript('''
            CREATE TABLE IF NOT EXISTS guilds (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                leader TEXT NOT NULL UNIQUE);
            CREATE TABLE IF NOT EXISTS guild_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL,
                kind TEXT NOT NULL, title TEXT NOT NULL, map_name TEXT NOT NULL,
                goal INTEGER NOT NULL, complete INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS guild_event_visits (
                event_id INTEGER NOT NULL, trainer TEXT NOT NULL,
                PRIMARY KEY(event_id, trainer));
            CREATE INDEX IF NOT EXISTS guild_events_guild ON guild_events(guild_id,id);
            CREATE TABLE IF NOT EXISTS guild_stats (
                guild_id INTEGER PRIMARY KEY, xp INTEGER NOT NULL DEFAULT 0,
                expeditions INTEGER NOT NULL DEFAULT 0, meetups INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS guild_members (
                trainer TEXT PRIMARY KEY, guild_id INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS guild_members_guild ON guild_members(guild_id);
            CREATE TABLE IF NOT EXISTS guild_invites (
                guild_id INTEGER NOT NULL, trainer TEXT NOT NULL,
                PRIMARY KEY(guild_id, trainer));
            CREATE TABLE IF NOT EXISTS guild_applications (
                guild_id INTEGER NOT NULL, trainer TEXT NOT NULL,
                PRIMARY KEY(guild_id, trainer));
            CREATE TABLE IF NOT EXISTS guild_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL,
                trainer TEXT NOT NULL, body TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS guild_posts_guild ON guild_posts(guild_id,id);
            CREATE TABLE IF NOT EXISTS guild_meetups (
                guild_id INTEGER PRIMARY KEY, map_name TEXT NOT NULL,
                goal INTEGER NOT NULL, complete INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS guild_expeditions (
                guild_id INTEGER PRIMARY KEY, map_name TEXT NOT NULL,
                goal INTEGER NOT NULL, complete INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS guild_expedition_visits (
                guild_id INTEGER NOT NULL, trainer TEXT NOT NULL,
                PRIMARY KEY(guild_id, trainer));
        ''')
        db.execute('INSERT OR IGNORE INTO guild_stats(guild_id) SELECT id FROM guilds')
        db.commit()

    def _identifier(self, value):
        if not isinstance(value, str) or not NAME.fullmatch(value):
            raise GuildError('Use 1-24 letters, numbers, underscores or hyphens.')
        return value

    def _member(self, trainer):
        return self.db.execute('SELECT g.id,g.name,g.leader FROM guilds g JOIN guild_members m ON m.guild_id=g.id WHERE m.trainer=?', (trainer,)).fetchone()

    def _require(self, trainer, leader=False):
        row = self._member(trainer)
        if not row: raise GuildError('You are not in a guild.')
        if leader and row[2] != trainer: raise GuildError('Only the guild leader can do that.')
        return row

    def members(self, trainer):
        guild = self._require(trainer)
        rows = self.db.execute('SELECT trainer FROM guild_members WHERE guild_id=? ORDER BY trainer COLLATE NOCASE,trainer', (guild[0],)).fetchall()
        return guild[1], [row[0] for row in rows]

    def command(self, trainer, command):
        self._identifier(trainer)
        if not isinstance(command, str) or len(command) > 120:
            raise GuildError('Invalid guild command.')
        words = command.split()
        if not words or words == ['help']:
            return ['protocol 1', '/guild create NAME | /guild invite TRAINER', '/guild list | /guild standings | /guild apply NAME | /guild invites', '/guild applications | /guild approve TRAINER | /guild reject TRAINER', '/guild info | /guild roster | /guild online | /guild leave', '/guild event starts a guild-wide journey: /guild event start here COUNT TITLE', '/guild event arrive ID | visit | list | cancel', '/guild post story ID CLUE adds a clue to the guild board.', '/guild expedition and /guild meet show group goals.', '/guild post MESSAGE | /guild board | /guild clear', '/guild kick TRAINER | /guild transfer TRAINER | /guild disband', '/g MESSAGE sends guild-only chat.']
        op, args = words[0].lower(), words[1:]
        if op in ('list','standings','apply','applications','approve','reject'):
            return self.recruit(trainer, op, args)
        if op == 'meet':
            return self.meet(trainer, args)
        if op == 'event':
            return self.event(trainer, args)
        if op == 'expedition':
            return self.expedition(trainer, args)
        if op == 'post' and len(args) >= 2 and args[0].lower() == 'story':
            return self.story_post(trainer, args[1:])
        if op in ('post','board','clear'):
            return self.board(trainer, op, command[len(words[0]):].strip())
        arity = {'create':1,'invite':1,'accept':1,'decline':1,'invites':0,'info':0,'roster':0,'leave':0,'kick':1,'transfer':1,'disband':0}
        if op not in arity or len(args) != arity[op]:
            raise GuildError('Invalid command. Use /guild help.')
        arg = self._identifier(args[0]) if args else None
        with self.db:
            if op == 'create':
                if self._member(trainer): raise GuildError('Leave your current guild first.')
                if self.db.execute('SELECT 1 FROM guilds WHERE name=? COLLATE NOCASE', (arg,)).fetchone(): raise GuildError('Guild name already taken.')
                cur=self.db.execute('INSERT INTO guilds(name,leader) VALUES(?,?)',(arg,trainer))
                self.db.execute('INSERT INTO guild_members VALUES(?,?)',(trainer,cur.lastrowid))
                self.db.execute('INSERT INTO guild_stats(guild_id) VALUES(?)',(cur.lastrowid,))
                self.db.execute('DELETE FROM guild_invites WHERE trainer=?',(trainer,))
                self.db.execute('DELETE FROM guild_applications WHERE trainer=?',(trainer,))
                return [f'Created {arg}. You are the leader.']
            if op in ('invite','kick','transfer'):
                guild=self._require(trainer,leader=True)
                if arg == trainer: raise GuildError('Choose another trainer.')
                if op=='invite':
                    if not self.db.execute('SELECT 1 FROM identities WHERE id=?',(arg,)).fetchone(): raise GuildError('Trainer does not exist in this world.')
                    if self._member(arg): raise GuildError('Trainer is already in a guild.')
                    count=self.db.execute('SELECT COUNT(*) FROM guild_members WHERE guild_id=?',(guild[0],)).fetchone()[0]
                    if count>=MAX_MEMBERS: raise GuildError('Guild is full.')
                    if not self.db.execute('SELECT 1 FROM guild_invites WHERE guild_id=? AND trainer=?',(guild[0],arg)).fetchone():
                        if self.db.execute('SELECT COUNT(*) FROM guild_invites WHERE guild_id=?',(guild[0],)).fetchone()[0] >= MAX_MEMBERS: raise GuildError('Guild has too many pending invitations.')
                        if self.db.execute('SELECT COUNT(*) FROM guild_invites WHERE trainer=?',(arg,)).fetchone()[0] >= MAX_MEMBERS: raise GuildError('Trainer has too many pending invitations.')
                    self.db.execute('INSERT OR IGNORE INTO guild_invites VALUES(?,?)',(guild[0],arg))
                    return [f'Invited {arg} to {guild[1]}.']
                if not self.db.execute('SELECT 1 FROM guild_members WHERE trainer=? AND guild_id=?',(arg,guild[0])).fetchone(): raise GuildError('Trainer is not in your guild.')
                if op=='kick':
                    self.db.execute('DELETE FROM guild_event_visits WHERE trainer=?',(arg,))
                    self.db.execute('DELETE FROM guild_members WHERE trainer=?',(arg,))
                    return [f'Removed {arg} from {guild[1]}.']
                self.db.execute('UPDATE guilds SET leader=? WHERE id=?',(arg,guild[0]))
                return [f'{arg} is now the leader of {guild[1]}.']
            if op in ('accept','decline'):
                invite=self.db.execute('SELECT g.id,g.name FROM guild_invites i JOIN guilds g ON g.id=i.guild_id WHERE i.trainer=? AND g.name=? COLLATE NOCASE',(trainer,arg)).fetchone()
                if not invite: raise GuildError('No invitation from that guild.')
                if op=='decline':
                    self.db.execute('DELETE FROM guild_invites WHERE guild_id=? AND trainer=?',(invite[0],trainer))
                    return [f'Declined {invite[1]}.']
                if self._member(trainer): raise GuildError('Leave your current guild first.')
                count=self.db.execute('SELECT COUNT(*) FROM guild_members WHERE guild_id=?',(invite[0],)).fetchone()[0]
                if count>=MAX_MEMBERS: raise GuildError('Guild is full.')
                self.db.execute('INSERT INTO guild_members VALUES(?,?)',(trainer,invite[0]))
                self.db.execute('DELETE FROM guild_invites WHERE trainer=?',(trainer,))
                self.db.execute('DELETE FROM guild_applications WHERE trainer=?',(trainer,))
                return [f'Joined {invite[1]}.']
            if op=='invites':
                names=[x[0] for x in self.db.execute('SELECT g.name FROM guild_invites i JOIN guilds g ON g.id=i.guild_id WHERE i.trainer=? ORDER BY g.name COLLATE NOCASE LIMIT 50',(trainer,))]
                return ['Invites: '+', '.join(names[i:i+4]) for i in range(0,len(names),4)] or ['No guild invitations.']
            if op in ('info','roster'):
                guild=self._require(trainer);name,people=self.members(trainer)
                if op=='info':
                    xp,expeditions,meetups=self.db.execute('SELECT xp,expeditions,meetups FROM guild_stats WHERE guild_id=?',(guild[0],)).fetchone()
                    return [f'Guild {name}. Leader: {guild[2]}. Members: {len(people)}/{MAX_MEMBERS}.', f'Guild level {1+xp//100} ({xp} guild XP). Expeditions: {expeditions}. Meetups: {meetups}.']
                return ['Members: '+', '.join(people[i:i+4]) for i in range(0,len(people),4)]
            guild=self._require(trainer)
            if op=='leave':
                if guild[2]==trainer: raise GuildError('Transfer leadership or disband first.')
                self.db.execute('DELETE FROM guild_event_visits WHERE trainer=?',(trainer,))
                self.db.execute('DELETE FROM guild_members WHERE trainer=?',(trainer,))
                return [f'Left {guild[1]}.']
            self._require(trainer,leader=True)
            self.db.execute('DELETE FROM guild_invites WHERE guild_id=?',(guild[0],))
            self.db.execute('DELETE FROM guild_applications WHERE guild_id=?',(guild[0],))
            self.db.execute('DELETE FROM guild_expedition_visits WHERE guild_id=?',(guild[0],))
            self.db.execute('DELETE FROM guild_expeditions WHERE guild_id=?',(guild[0],))
            self.db.execute('DELETE FROM guild_event_visits WHERE event_id IN (SELECT id FROM guild_events WHERE guild_id=?)',(guild[0],))
            self.db.execute('DELETE FROM guild_events WHERE guild_id=?',(guild[0],))
            self.db.execute('DELETE FROM guild_meetups WHERE guild_id=?',(guild[0],))
            self.db.execute('DELETE FROM guild_posts WHERE guild_id=?',(guild[0],))
            self.db.execute('DELETE FROM guild_stats WHERE guild_id=?',(guild[0],))
            self.db.execute('DELETE FROM guild_members WHERE guild_id=?',(guild[0],))
            self.db.execute('DELETE FROM guilds WHERE id=?',(guild[0],))
            return [f'Disbanded {guild[1]}.']

    def recruit(self, trainer, op, args):
        """Public discovery and consent-based membership applications."""
        with self.db:
            if op=='list':
                if len(args)>1 or (args and (not args[0].isascii() or not args[0].isdecimal() or len(args[0])>3)):
                    raise GuildError('Use /guild list or /guild list PAGE.')
                page=int(args[0]) if args else 1
                total=self.db.execute('SELECT COUNT(*) FROM guilds').fetchone()[0]
                pages=max(1,(total+7)//8)
                if not 1<=page<=pages: raise GuildError(f'Page must be 1-{pages}.')
                rows=self.db.execute('SELECT g.name,g.leader,COUNT(m.trainer) FROM guilds g LEFT JOIN guild_members m ON m.guild_id=g.id GROUP BY g.id ORDER BY g.name COLLATE NOCASE,g.id LIMIT 8 OFFSET ?',((page-1)*8,)).fetchall()
                return [f'Guilds {page}/{pages}:']+([f'{name}: {count}/{MAX_MEMBERS}, leader {leader}' for name,leader,count in rows] or ['No guilds yet.'])
            if op=='standings':
                if len(args)>1 or (args and (not args[0].isascii() or not args[0].isdecimal() or len(args[0])>3)):
                    raise GuildError('Use /guild standings or /guild standings PAGE.')
                page=int(args[0]) if args else 1
                total=self.db.execute('SELECT COUNT(*) FROM guilds').fetchone()[0];pages=max(1,(total+7)//8)
                if not 1<=page<=pages: raise GuildError(f'Page must be 1-{pages}.')
                rows=self.db.execute('SELECT g.name,s.xp FROM guilds g JOIN guild_stats s ON s.guild_id=g.id ORDER BY s.xp DESC,g.name COLLATE NOCASE,g.id LIMIT 8 OFFSET ?',((page-1)*8,)).fetchall()
                return [f'Guild standings {page}/{pages}:']+([f'{name}: level {1+xp//100}, {xp} guild XP' for name,xp in rows] or ['No guilds yet.'])
            if op=='apply':
                if len(args)!=1: raise GuildError('Use /guild apply NAME.')
                self._identifier(args[0])
                if self._member(trainer): raise GuildError('Leave your current guild first.')
                guild=self.db.execute('SELECT id,name FROM guilds WHERE name=? COLLATE NOCASE',(args[0],)).fetchone()
                if not guild: raise GuildError('Guild does not exist.')
                if self.db.execute('SELECT COUNT(*) FROM guild_members WHERE guild_id=?',(guild[0],)).fetchone()[0]>=MAX_MEMBERS: raise GuildError('Guild is full.')
                if not self.db.execute('SELECT 1 FROM guild_applications WHERE guild_id=? AND trainer=?',(guild[0],trainer)).fetchone():
                    if self.db.execute('SELECT COUNT(*) FROM guild_applications WHERE guild_id=?',(guild[0],)).fetchone()[0]>=MAX_MEMBERS: raise GuildError('Guild has too many pending applications.')
                    if self.db.execute('SELECT COUNT(*) FROM guild_applications WHERE trainer=?',(trainer,)).fetchone()[0]>=MAX_MEMBERS: raise GuildError('You have too many pending applications.')
                self.db.execute('INSERT OR IGNORE INTO guild_applications VALUES(?,?)',(guild[0],trainer))
                return [f'Applied to {guild[1]}.']
            guild=self._require(trainer,leader=True)
            if op=='applications':
                if args: raise GuildError('Use /guild applications.')
                names=[r[0] for r in self.db.execute('SELECT trainer FROM guild_applications WHERE guild_id=? ORDER BY trainer COLLATE NOCASE,trainer',(guild[0],))]
                return ['Apply: '+', '.join(names[i:i+4]) for i in range(0,len(names),4)] or ['No pending guild applications.']
            if op not in ('approve','reject') or len(args)!=1: raise GuildError('Use /guild approve TRAINER or reject TRAINER.')
            self._identifier(args[0]);applicant=args[0]
            if not self.db.execute('SELECT 1 FROM guild_applications WHERE guild_id=? AND trainer=?',(guild[0],applicant)).fetchone(): raise GuildError('No application from that trainer.')
            if op=='reject':
                self.db.execute('DELETE FROM guild_applications WHERE guild_id=? AND trainer=?',(guild[0],applicant))
                return [f'Rejected {applicant}.']
            if self._member(applicant): raise GuildError('Trainer is already in a guild.')
            if self.db.execute('SELECT COUNT(*) FROM guild_members WHERE guild_id=?',(guild[0],)).fetchone()[0]>=MAX_MEMBERS: raise GuildError('Guild is full.')
            self.db.execute('INSERT INTO guild_members VALUES(?,?)',(applicant,guild[0]))
            self.db.execute('DELETE FROM guild_invites WHERE trainer=?',(applicant,))
            self.db.execute('DELETE FROM guild_applications WHERE trainer=?',(applicant,))
            return [f'Approved {applicant} for {guild[1]}.']

    def board(self, trainer, op, body):
        """Small persistent guild bulletin board; posts are untrusted player text."""
        with self.db:
            guild=self._require(trainer,leader=(op=='clear'))
            if op=='post':
                if not 1<=len(body)<=70 or not body.isascii() or any(ord(c)<32 or ord(c)>126 for c in body):
                    raise GuildError('Use /guild post followed by 1-70 printable characters.')
                self.db.execute('INSERT INTO guild_posts(guild_id,trainer,body) VALUES(?,?,?)',(guild[0],trainer,body))
                self.db.execute('DELETE FROM guild_posts WHERE guild_id=? AND id NOT IN (SELECT id FROM guild_posts WHERE guild_id=? ORDER BY id DESC LIMIT 20)',(guild[0],guild[0]))
                return ['Posted to the guild board.']
            if body: raise GuildError('This command takes no extra text.')
            if op=='clear':
                self.db.execute('DELETE FROM guild_posts WHERE guild_id=?',(guild[0],))
                return ['Guild board cleared.']
            rows=self.db.execute('SELECT trainer,body FROM guild_posts WHERE guild_id=? ORDER BY id DESC LIMIT 8',(guild[0],)).fetchall()
            return [f'{name}: {text}' for name,text in reversed(rows)] or ['Guild board is empty.']

    def meet(self, trainer, args):
        """A shared goal requiring members to be present together."""
        with self.db:
            guild=self._require(trainer)
            if not args:
                row=self.db.execute('SELECT map_name,goal,complete FROM guild_meetups WHERE guild_id=?',(guild[0],)).fetchone()
                if not row: return ['No meetup. Leader: /guild meet start here COUNT']
                return [f'Meetup: {row[1]} trainers together at {row[0]} ({"complete" if row[2] else "active"}).']
            self._require(trainer,leader=True)
            if args == ['cancel']:
                removed=self.db.execute('DELETE FROM guild_meetups WHERE guild_id=?',(guild[0],)).rowcount
                return ['Meetup cancelled.' if removed else 'No meetup to cancel.']
            if len(args)!=3 or args[0].lower()!='start' or not args[2].isascii() or not args[2].isdecimal() or len(args[2])>2:
                raise GuildError('Use /guild meet start MAP COUNT or cancel.')
            name=self.maps.get(args[1].lower())
            if not name: raise GuildError('Unknown map. Use a canonical World map name, e.g. Route101.')
            goal=int(args[2]);count=self.db.execute('SELECT COUNT(*) FROM guild_members WHERE guild_id=?',(guild[0],)).fetchone()[0]
            if not 2<=goal<=min(count,MAX_MEMBERS): raise GuildError('COUNT must be 2 through your current guild size.')
            current=self.db.execute('SELECT complete FROM guild_meetups WHERE guild_id=?',(guild[0],)).fetchone()
            if current and not current[0]: raise GuildError('Finish or cancel the active meetup first.')
            self.db.execute('INSERT OR REPLACE INTO guild_meetups VALUES(?,?,?,0)',(guild[0],name,goal))
            return [f'Meetup started: {goal} trainers together at {name}.']

    def active_meet(self, trainer, map_name):
        guild=self._member(trainer)
        if not guild:return False
        row=self.db.execute('SELECT 1 FROM guild_meetups WHERE guild_id=? AND map_name=? AND complete=0',(guild[0],map_name)).fetchone()
        return row is not None

    def complete_meet(self, trainer, map_name, ready_members):
        """Complete once when enough current guildmates are simultaneously present."""
        with self.db:
            guild=self._member(trainer)
            if not guild:return None
            row=self.db.execute('SELECT map_name,goal,complete FROM guild_meetups WHERE guild_id=?',(guild[0],)).fetchone()
            if not row or row[2] or row[0]!=map_name:return None
            _,members=self.members(trainer)
            if len(set(ready_members).intersection(members))<row[1]:return None
            self.db.execute('UPDATE guild_meetups SET complete=1 WHERE guild_id=?',(guild[0],))
            self.db.execute('UPDATE guild_stats SET xp=MIN(xp+15,1000000000),meetups=MIN(meetups+1,1000000000) WHERE guild_id=?',(guild[0],))
            return guild[1],row[0],row[1],members

    def expedition(self, trainer, args):
        """A cooperative visit objective. Arrival is client-reported, not anti-cheat."""
        with self.db:
            guild=self._require(trainer)
            if not args:
                row=self.db.execute('SELECT map_name,goal,complete FROM guild_expeditions WHERE guild_id=?',(guild[0],)).fetchone()
                if not row: return ['No expedition. Leader: /guild expedition start here COUNT']
                count=self.db.execute('SELECT COUNT(*) FROM guild_expedition_visits WHERE guild_id=?',(guild[0],)).fetchone()[0]
                state='complete' if row[2] else 'active'
                return [f'Expedition: {row[0]} {count}/{row[1]} trainers ({state}).']
            self._require(trainer,leader=True)
            if args == ['cancel']:
                self.db.execute('DELETE FROM guild_expedition_visits WHERE guild_id=?',(guild[0],))
                removed=self.db.execute('DELETE FROM guild_expeditions WHERE guild_id=?',(guild[0],)).rowcount
                return ['Expedition cancelled.' if removed else 'No expedition to cancel.']
            if len(args)!=3 or args[0].lower()!='start' or not args[2].isascii() or not args[2].isdecimal() or len(args[2])>2:
                raise GuildError('Use /guild expedition start MAP COUNT or cancel.')
            name=self.maps.get(args[1].lower())
            if not name: raise GuildError('Unknown map. Use a canonical World map name, e.g. Route101.')
            goal=int(args[2]); member_count=self.db.execute('SELECT COUNT(*) FROM guild_members WHERE guild_id=?',(guild[0],)).fetchone()[0]
            if not 1<=goal<=min(member_count,MAX_MEMBERS): raise GuildError('COUNT must be 1 through your current guild size.')
            current=self.db.execute('SELECT complete FROM guild_expeditions WHERE guild_id=?',(guild[0],)).fetchone()
            if current and not current[0]: raise GuildError('Finish or cancel the active expedition first.')
            self.db.execute('DELETE FROM guild_expedition_visits WHERE guild_id=?',(guild[0],))
            self.db.execute('INSERT OR REPLACE INTO guild_expeditions VALUES(?,?,?,0)',(guild[0],name,goal))
            return [f'Expedition started: {goal} trainers visit {name}.']

    def event(self, trainer, args):
        """A replayable guild objective that gives members a shared destination."""
        if not args or args == ['list']:
            with self.db:
                guild = self._require(trainer)
                rows = self.db.execute('SELECT id,title,map_name,goal,complete FROM guild_events WHERE guild_id=? ORDER BY id DESC LIMIT 5', (guild[0],)).fetchall()
                if not rows: return ['No guild journeys yet. Leader: /guild event start here COUNT TITLE']
                return [f'#{event_id} {title} at {map_name}: {self.db.execute("SELECT COUNT(*) FROM guild_event_visits WHERE event_id=?", (event_id,)).fetchone()[0]}/{goal} explorers ({"complete" if complete else "active"}).' for event_id,title,map_name,goal,complete in reversed(rows)]
        with self.db:
            guild = self._require(trainer)
            op = args[0].lower()
            if op not in ('cancel', 'visit', 'arrive', 'start'):
                raise GuildError('Use /guild event start here COUNT TITLE, /guild event arrive ID, visit or cancel.')
            if op == 'cancel' and len(args) == 1:
                self._require(trainer, leader=True)
                active = self.db.execute('SELECT id FROM guild_events WHERE guild_id=? AND complete=0', (guild[0],)).fetchone()
                if not active:
                    return ['No active guild journey.']
                self.db.execute('DELETE FROM guild_event_visits WHERE event_id IN (SELECT id FROM guild_events WHERE guild_id=? AND complete=0)', (guild[0],))
                self.db.execute('UPDATE guild_events SET complete=1 WHERE guild_id=? AND complete=0', (guild[0],))
                return ['Guild journey cancelled.']
            if op == 'visit' and len(args) == 1:
                active = self.db.execute('SELECT id,map_name,goal FROM guild_events WHERE guild_id=? AND complete=0 ORDER BY id DESC LIMIT 1', (guild[0],)).fetchone()
                if not active: return ['No active guild journey.']
                return [f'Journey #{active[0]}: {active[1]}, {active[2]} members needed. Use /guild event arrive ID in the field.']

            if op == 'arrive' and len(args) == 2 and args[1].isascii() and args[1].isdecimal() and len(args[1]) <= 10:
                event_id = int(args[1])
                row = self.db.execute('SELECT guild_id,map_name,goal,complete FROM guild_events WHERE id=?', (event_id,)).fetchone()
                if not row or row[0] != guild[0] or row[3]:
                    raise GuildError('That guild journey is no longer active.')
                self.db.execute('INSERT OR IGNORE INTO guild_event_visits(event_id,trainer) VALUES(?,?)', (event_id, trainer))
                count = self.db.execute('SELECT COUNT(*) FROM guild_event_visits WHERE event_id=?', (event_id,)).fetchone()[0]
                if count >= row[2]:
                    self.db.execute('UPDATE guild_events SET complete=1 WHERE id=? AND complete=0', (event_id,))
                    self.db.execute('UPDATE guild_stats SET xp=MIN(xp+20,1000000000),expeditions=MIN(expeditions+1,1000000000) WHERE guild_id=?', (guild[0],))
                    return [f'Guild journey complete at {row[1]}! {count} members found the place. The guild earned 20 XP.']
                return [f'You reached {row[1]}. {count}/{row[2]} guild members have arrived.']
            if op != 'start' or len(args) < 5 or args[1].lower() != 'here':
                raise GuildError('Use /guild event start here COUNT MAP TITLE, /guild event arrive ID, visit or cancel.')
            self._require(trainer, leader=True)
            if not args[2].isascii() or not args[2].isdecimal() or len(args[2]) > 2:
                raise GuildError('COUNT must be a number from 2 through your guild size.')
            name = self.maps.get(args[3].lower())
            if not name:
                raise GuildError('Unknown map. Use a canonical World map name.')
            title = ' '.join(args[4:]).strip()
            if not 1 <= len(title) <= 48 or not title.isascii() or any(ord(c) < 32 or ord(c) > 126 for c in title):
                raise GuildError('Use a 1-48 character printable ASCII journey title.')
            goal = int(args[2])
            count = self.db.execute('SELECT COUNT(*) FROM guild_members WHERE guild_id=?', (guild[0],)).fetchone()[0]
            if not 2 <= goal <= min(count, MAX_MEMBERS):
                raise GuildError('COUNT must be 2 through your current guild size.')
            active = self.db.execute('SELECT 1 FROM guild_events WHERE guild_id=? AND complete=0', (guild[0],)).fetchone()
            if active:
                raise GuildError('Finish or cancel the active guild story first.')
            cur = self.db.execute('INSERT INTO guild_events(guild_id,kind,title,map_name,goal) VALUES(?,?,?,?,?)',
                                  (guild[0], 'discovery', title, name, goal))
            self.db.execute('INSERT INTO guild_event_visits(event_id,trainer) VALUES(?,?)', (cur.lastrowid, trainer))
            return [f'Guild story started: {title}. Meet {goal} members at {name}; you are already counted.']

    def story_post(self, trainer, args):
        """Give guild members a player-written clue for their active shared journey."""
        if len(args) < 2 or not args[0].isascii() or not args[0].isdecimal() or len(args[0]) > 10:
            raise GuildError('Use /guild post story ID followed by a 1-70 character clue.')
        event_id = int(args[0])
        clue = ' '.join(args[1:]).strip()
        if not 1 <= len(clue) <= 70 or not clue.isascii() or any(ord(c) < 32 or ord(c) > 126 for c in clue):
            raise GuildError('Use a 1-70 character printable ASCII clue.')
        with self.db:
            guild = self._require(trainer)
            row = self.db.execute('SELECT guild_id,complete FROM guild_events WHERE id=?', (event_id,)).fetchone()
            if not row or row[0] != guild[0] or row[1]:
                raise GuildError('That guild journey is no longer active.')
            body = f'[Journey #{event_id} clue] {clue}'
            self.db.execute('INSERT INTO guild_posts(guild_id,trainer,body) VALUES(?,?,?)', (guild[0], trainer, body))
            self.db.execute('DELETE FROM guild_posts WHERE guild_id=? AND id NOT IN (SELECT id FROM guild_posts WHERE guild_id=? ORDER BY id DESC LIMIT 20)', (guild[0], guild[0]))
            return ['Clue added to the guild board.']

    def visit(self, trainer, map_name):
        """Record a distinct member's validated field report, returning completion recipients."""
        with self.db:
            guild=self._member(trainer)
            if not guild: return None
            row=self.db.execute('SELECT map_name,goal,complete FROM guild_expeditions WHERE guild_id=?',(guild[0],)).fetchone()
            if not row or row[2] or row[0] != map_name: return None
            self.db.execute('INSERT OR IGNORE INTO guild_expedition_visits VALUES(?,?)',(guild[0],trainer))
            count=self.db.execute('SELECT COUNT(*) FROM guild_expedition_visits WHERE guild_id=?',(guild[0],)).fetchone()[0]
            if count < row[1]: return None
            self.db.execute('UPDATE guild_expeditions SET complete=1 WHERE guild_id=?',(guild[0],))
            self.db.execute('UPDATE guild_stats SET xp=MIN(xp+10,1000000000),expeditions=MIN(expeditions+1,1000000000) WHERE guild_id=?',(guild[0],))
            return guild[1],row[0],row[1],self.members(trainer)[1]
