"""One opt-in guild entry point for existing RC12 field activities.

Only explicit host adverts expose invitations. No clues, choices or results are
copied into the board. Underlying activity systems remain authoritative.
"""
import json
from .guilds import GuildError


class ActivityBoard:
    def __init__(self,server):self.s=server;self.adverts={}

    def catalog(self):
        result=[]
        for kind,table in [('mystery','mystery_packs'),('relay','relay_courses'),('flag','flag_arenas')]:
            for key,raw in self.s.db.execute(f'SELECT id,document FROM {table} ORDER BY id'):
                doc=json.loads(raw)
                points=([x['at'] for x in doc['stages'][0]['stations']] if kind=='mystery' else
                        [x['start'] for x in doc['legs']] if kind=='relay' else doc['bases'])
                result.append(dict(kind=kind,id=key,title=doc['title'],players=len(points),at=points[0]))
        return result

    def current(self,name,kind):
        if kind=='mystery':
            r=self.s.mysteries._current(name)
            if not r:return None
            return dict(id=r[0],key=r[1],host=self.s.db.execute('SELECT trainer FROM mystery_members WHERE run=? AND role=0',(r[0],)).fetchone()[0],open=r[3]=='waiting')
        r=(self.s.relays._current(name) if kind=='relay' else self.s.flags.current(name))
        if not r:return None
        return dict(id=r['id'],key=r['course']['id'] if kind=='relay' else r['arena']['id'],host=r['members'][0]['id'],open=r['phase']=='lobby' and len(r['members'])<(len(r['course']['legs']) if kind=='relay' else 2))

    def prune(self):
        self.s.relays.tick();self.s.flags.tick()
        for host,a in list(self.adverts.items()):
            member=self.s.guilds._member(host);peer=self.s.peers.get(host);r=self.current(host,a['kind'])
            if (not member or member[0]!=a['guild'] or not peer or peer.get('closing') or peer is not a['peer']
                    or not r or r['id']!=a['run'] or not r['open']):self.adverts.pop(host,None)

    def dispatch(self,c,kind,words):
        try:
            if kind=='mystery':return self.s.mysteries.command(c['id'],words)
            return (self.s.relays if kind=='relay' else self.s.flags).command(c,words)
        except ValueError as exc:raise GuildError(str(exc)) from None

    def command(self,c,words):
        if not c.get('private_commands'):raise GuildError('Activities need the matched RC12 private-command client.')
        guild=self.s.guilds._require(c['id']);self.prune()
        kinds=('mystery','relay','flag')
        if not words:return ['Activity board: /guild play list or /guild play open',
            'Start: /guild play start KIND ID. Resume: /guild play status',
            'Host opt-in: /guild play share KIND advertises to your guild.',
            'Sharing exposes host, activity and join code, never clues or choices.',
            'Hide your advert: /guild play hide. This does not cancel your activity.']
        if words[0]=='list' and len(words)<=2:
            page=words[1] if len(words)==2 else '1'
            if not page.isascii() or not page.isdecimal() or not 1<=int(page)<=100:raise GuildError('Use /guild play list PAGE (1..100).')
            items=self.catalog();start=(int(page)-1)*4
            lines=[f'Installed activities: page {page}/{max(1,(len(items)+3)//4)}.']
            for a in items[start:start+4]:
                lines += [f"{a['kind']} {a['id']}: {a['title']}",
                          f"{a['players']} players; start near "+self.s.relays._location(a['at']),
                          f"/guild play start {a['kind']} {a['id']}"]
            return lines+['After a completed mystery, /story at its final location shows unlocked follow-up choices.']
        if words==['open']:
            lines=['Your guild hosts explicitly shared these invitations:']
            for host,a in list(self.adverts.items()):
                if a['guild']==guild[0]:lines += [host+': '+a['kind']+' '+a['key'],f"/guild play join {host}"]
                if len(lines)>=13:break
            return lines if len(lines)>1 else ['No shared invitations. Start an activity, then /guild play share KIND to invite guildmates.']
        if words==['hide']:
            self.adverts.pop(c['id'],None);return ['Your board invitation is hidden. Existing participants and activity are unchanged.']
        if len(words)==2 and words[0]=='share' and words[1] in kinds:
            r=self.current(c['id'],words[1])
            if not r or r['host']!=c['id'] or not r['open']:raise GuildError('Only the host of an open activity can advertise it.')
            if len(self.adverts)>=64 and c['id'] not in self.adverts:raise GuildError('Board full. Try later.')
            self.adverts[c['id']]=dict(guild=guild[0],kind=words[1],key=r['key'],run=r['id'],peer=c)
            return ['Your guild can now see your host name, activity and invitation via /guild play open.',
                    '/guild play hide removes it. Private clues, choices and scores are not advertised.']
        if words==['status']:
            lines=[]
            for kind in kinds:
                if self.current(c['id'],kind):
                    lines += [kind.upper()+':']+self.dispatch(c,kind,['status'])
            return lines[:15] or ['No active activity. /guild play list to choose one; /guild play open to find a partner.']
        if len(words)==3 and words[0]=='start' and words[1] in kinds:
            return self.dispatch(c,words[1],['start',words[2]])+['To invite guildmates publicly within your guild: /guild play share '+words[1]]
        if len(words)==2 and words[0]=='join':
            a=self.adverts.get(words[1])
            if not a or a['guild']!=guild[0] or words[1]==c['id']:raise GuildError('That shared invitation is unavailable to you.')
            lines=self.dispatch(c,a['kind'],['join',a['run']]);self.prune();return lines
        raise GuildError('Use /guild play list, open, start KIND ID, join HOST, share KIND, hide, or status.')
