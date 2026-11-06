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
    def __init__(self, db):
        self.db = db
        db.executescript('''
            CREATE TABLE IF NOT EXISTS guilds (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                leader TEXT NOT NULL UNIQUE);
            CREATE TABLE IF NOT EXISTS guild_members (
                trainer TEXT PRIMARY KEY, guild_id INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS guild_members_guild ON guild_members(guild_id);
            CREATE TABLE IF NOT EXISTS guild_invites (
                guild_id INTEGER NOT NULL, trainer TEXT NOT NULL,
                PRIMARY KEY(guild_id, trainer));
        ''')

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
            return ['/guild create NAME | /guild invite TRAINER', '/guild invites | /guild accept NAME | /guild decline NAME', '/guild info | /guild roster | /guild leave', '/guild kick TRAINER | /guild transfer TRAINER | /guild disband', '/g MESSAGE sends guild-only chat.']
        op, args = words[0].lower(), words[1:]
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
                self.db.execute('DELETE FROM guild_invites WHERE trainer=?',(trainer,))
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
                return [f'Joined {invite[1]}.']
            if op=='invites':
                names=[x[0] for x in self.db.execute('SELECT g.name FROM guild_invites i JOIN guilds g ON g.id=i.guild_id WHERE i.trainer=? ORDER BY g.name COLLATE NOCASE LIMIT 50',(trainer,))]
                return ['Invites: '+', '.join(names[i:i+4]) for i in range(0,len(names),4)] or ['No guild invitations.']
            if op in ('info','roster'):
                guild=self._require(trainer);name,people=self.members(trainer)
                if op=='info': return [f'Guild {name}. Leader: {guild[2]}. Members: {len(people)}/{MAX_MEMBERS}.']
                return ['Members: '+', '.join(people[i:i+4]) for i in range(0,len(people),4)]
            guild=self._require(trainer)
            if op=='leave':
                if guild[2]==trainer: raise GuildError('Transfer leadership or disband first.')
                self.db.execute('DELETE FROM guild_members WHERE trainer=?',(trainer,))
                return [f'Left {guild[1]}.']
            self._require(trainer,leader=True)
            self.db.execute('DELETE FROM guild_invites WHERE guild_id=?',(guild[0],))
            self.db.execute('DELETE FROM guild_members WHERE guild_id=?',(guild[0],))
            self.db.execute('DELETE FROM guilds WHERE id=?',(guild[0],))
            return [f'Disbanded {guild[1]}.']
