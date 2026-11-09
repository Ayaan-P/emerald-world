"""Pinned canonical-story reactions to explicitly shared authority history.

CORE1 is an adapter contract, not proof of native save completion. Only a native
safe-point adapter may offer these packets to the game. No save flags are written.
"""
import hashlib
import json
import re
import time


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


# Keep native hook identities and allowed changes reviewable. Agents can author
# another version, but cannot supply script pointers, flag writes or battle code.
BEATS = {
    'woods_rescued': {'map': 'PetalburgWoods', 'requires': None,
        'hook': 'PetalburgWoods_EventScript_RemoveDevonResearcher',
        'proof': 'VAR_PETALBURG_WOODS_STATE == 1',
        'outcome': 'devon_warned',
        'public': 'Explorers warned Devon about the Aqua ambush in Petalburg Woods.'},
    'goods_recovered': {'map': 'RusturfTunnel', 'requires': 'woods_rescued',
        'hook': 'RusturfTunnel_EventScript_Grunt',
        'proof': 'FLAG_RECOVERED_DEVON_GOODS after reward and rescue completion',
        'outcome': 'devon_goods_secured',
        'public': 'Explorers recovered Devon goods and rescued Peeko in Rusturf Tunnel.'},
}
CHECKPOINTS = {
    'rusturf_grunt': {'map': 'RusturfTunnel', 'requires': 'woods_rescued',
        'completed': 'goods_recovered', 'outcome': 'devon_warned',
        'hook': 'RusturfTunnel_EventScript_Grunt before trainerbattle_no_intro',
        'baseline': 'The Aqua thief has cornered Peeko. Recover the Devon goods and bring Peeko home.',
        'changed': 'Devon received a warning about the Woods ambush. Their courier asks you to protect Peeko first, then recover the stolen goods.',
        'objective': 'Defeat the Aqua grunt and finish the Peeko rescue.'},
    'devon_return': {'map': 'RustboroCity_DevonCorp_3F', 'requires': 'goods_recovered',
        'completed': 'devon_met', 'outcome': 'devon_goods_secured',
        'hook': 'RustboroCity_DevonCorp_3F_EventScript_MeetPresident before MrStoneIHaveFavor',
        'baseline': 'Devon is waiting for news of the stolen goods.',
        'changed': 'Word of the Rusturf rescue has reached Devon. The staff recognize the explorers who kept the delivery route open.',
        'objective': 'Speak with the Devon president and continue your own delivery assignment.'},
}


class CoreStory:
    def __init__(self, server):
        self.s = server
        self.db = server.db
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS canonical_reflections(
            id TEXT PRIMARY KEY, trainer TEXT, actor TEXT, run TEXT, fingerprint TEXT, context TEXT,
            status TEXT, created REAL, lease TEXT, reply TEXT, interpretation TEXT, version INTEGER,
            UNIQUE(trainer,actor));
        CREATE TABLE IF NOT EXISTS canonical_perspectives(
            trainer TEXT, run TEXT, actor TEXT, interpretation TEXT NOT NULL,
            reflection TEXT NOT NULL, updated REAL NOT NULL, PRIMARY KEY(trainer,run,actor));
        CREATE TABLE IF NOT EXISTS canonical_memory_optin(trainer TEXT,actor TEXT,PRIMARY KEY(trainer,actor));
        CREATE TABLE IF NOT EXISTS canonical_encounters(
            trainer TEXT, run TEXT, actor TEXT, talks INTEGER, updated REAL, version INTEGER, goal TEXT, text TEXT,
            PRIMARY KEY(trainer,run,actor));
        CREATE TABLE IF NOT EXISTS canonical_intent_receipts(
            actor TEXT, intention TEXT, action_receipt INTEGER NOT NULL, PRIMARY KEY(actor,intention));
        CREATE TABLE IF NOT EXISTS canonical_contributions(
            seq INTEGER PRIMARY KEY, course TEXT NOT NULL, actor TEXT NOT NULL, owner TEXT NOT NULL,
            text TEXT NOT NULL, status TEXT NOT NULL, UNIQUE(course,actor));
        CREATE TABLE IF NOT EXISTS character_journey_receipts(
            actor TEXT, journey TEXT, seq INTEGER NOT NULL, PRIMARY KEY(actor,journey));
        CREATE TABLE IF NOT EXISTS canonical_construction_receipts(
            actor TEXT, intention TEXT, signature TEXT NOT NULL, revision TEXT NOT NULL, seq INTEGER NOT NULL,
            PRIMARY KEY(actor,intention));
        CREATE TABLE IF NOT EXISTS canonical_studies(
            revision TEXT PRIMARY KEY, actor TEXT NOT NULL, digest TEXT NOT NULL, document TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS canonical_projects(
            course TEXT PRIMARY KEY, actor TEXT NOT NULL, digest TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS canonical_conversations(
            trainer TEXT, actor TEXT, version INTEGER NOT NULL, choice TEXT NOT NULL,
            PRIMARY KEY(trainer,actor));
        CREATE TABLE IF NOT EXISTS core_story_progress(
            trainer TEXT, run TEXT, beat TEXT, PRIMARY KEY(trainer,run,beat));
        CREATE TABLE IF NOT EXISTS core_story_shared(
            trainer TEXT, run TEXT, beat TEXT, seq INTEGER, PRIMARY KEY(trainer,run,beat));
        CREATE TABLE IF NOT EXISTS core_story_offers(
            trainer TEXT, run TEXT, checkpoint TEXT, document TEXT,
            PRIMARY KEY(trainer,run,checkpoint));
        ''')
        self.db.commit()

    def contract(self):
        return dict(schema=1, adapter='CORE1', native_connected=False,
                    beats=BEATS, checkpoints=CHECKPOINTS,
                    effects=['supplemental_briefing', 'objective_hint'],
                    boundaries=['Native completion reports are client attestations, not anti-cheat proof.',
                                'No native flag, item, trainer team or original script replacement.',
                                'Private progress never enters world recall without explicit sharing.',
                                'Offers are pinned for a save lineage; ordinary offline story continues.'])

    def _has(self, trainer, run, beat):
        return self.db.execute('SELECT 1 FROM core_story_progress WHERE trainer=? AND run=? AND beat=?',
                               (trainer, run, beat)).fetchone() is not None

    def _place(self, conn, name):
        from .build_catalog import catalog_maps
        state = conn.get('state')
        if (not state or time.monotonic()-conn.get('state_time', 0)>3
                or catalog_maps().get(tuple(state[:2]), {}).get('name') != name):
            raise ValueError('Canonical checkpoint location is unavailable.')

    def handle(self, conn, fields):
        # A separate negotiated protocol, never a chat command or chat reply.
        if (not conn.get('core_story_capable') or self.s.peers.get(conn.get('id')) is not conn
                or conn.get('closing')):
            raise ValueError('Canonical story adapter was not negotiated.')
        if (len(fields) != 5 or fields[0] != 'CORE' or
                not re.fullmatch('[0-9a-f]{32}', fields[1])):
            raise ValueError('Invalid canonical story request.')
        _, run, action, key, confirmation = fields
        trainer = conn['id']
        if action=='SEEN' and re.fullmatch('[0-9a-f]{64}',confirmation):
            from .canonical_cast import location
            from .canonical_memory import acknowledge
            actor,map_name=location(key)
            if actor is None:raise ValueError('Unknown actor.')
            return acknowledge(self.s,conn,run,actor,confirmation,map_name=map_name)
        if action == 'CAST' and confirmation == 'safe':
            from .canonical_cast import response
            return response(self.s,conn,run,key)
        with self.db:
            if action == 'SYNC' and confirmation == 'private':
                if key not in ('0','1','3','7'):
                    raise ValueError('Invalid canonical progress snapshot.')
                if not conn.get('state') or time.monotonic()-conn.get('state_time',0)>3:
                    raise ValueError('Native field snapshot is unavailable.')
                names=('woods_rescued','goods_recovered','devon_met')
                old={row[0] for row in self.db.execute(
                    'SELECT beat FROM core_story_progress WHERE trainer=? AND run=?',(trainer,run))}
                current={name for i,name in enumerate(names) if int(key)&(1<<i)}
                if old-current:
                    self.db.execute('DELETE FROM core_story_offers WHERE trainer=? AND run=?',(trainer,run))
                self.db.execute('DELETE FROM core_story_progress WHERE trainer=? AND run=?',(trainer,run))
                self.db.executemany('INSERT INTO core_story_progress VALUES(?,?,?)',
                                    ((trainer,run,name) for name in current))
                conn['core_active_run']=run
                return dict(schema=1,run=run,progress=int(key),source='native_client_attestation')
            if action == 'REPORT' and confirmation == 'complete':
                beat = BEATS.get(key)
                if beat is None:
                    raise ValueError('Unknown canonical completion.')
                self._place(conn, beat['map'])
                if beat['requires'] and not self._has(trainer, run, beat['requires']):
                    raise ValueError('This save lineage has not reported its prerequisite.')
                self.db.execute('INSERT OR IGNORE INTO core_story_progress VALUES(?,?,?)', (trainer,run,key))
                shared = self.db.execute('SELECT 1 FROM core_story_shared WHERE trainer=? AND run=? AND beat=?', (trainer,run,key)).fetchone() is not None
                return dict(schema=1, run=run, beat=key, recorded=True, shared=shared,
                            source='native_client_attestation', share_preview=beat['public'])
            if action == 'SHARE' and confirmation == 'confirm':
                beat = BEATS.get(key)
                if beat is None or not self._has(trainer,run,key):
                    raise ValueError('No completed beat is available to share.')
                old = self.db.execute('SELECT seq FROM core_story_shared WHERE trainer=? AND run=? AND beat=?',
                                      (trainer,run,key)).fetchone()
                if old:
                    seq = old[0]
                else:
                    # Public payload deliberately excludes trainer/run, dialogue,
                    # private choice, party, save state and arbitrary client text.
                    seq = self.s.memory.append('canonical_story_outcome', dict(
                        arc='devon_aqua_v1', beat=key, outcome=beat['outcome'],
                        summary=beat['public'], places=['native:'+beat['map']],
                        source='explicitly_shared_native_attestation'))
                    self.db.execute('INSERT INTO core_story_shared VALUES(?,?,?,?)',(trainer,run,key,seq))
                return dict(schema=1, run=run, beat=key, shared=True, evidence=seq)
            if action == 'OFFER' and confirmation == 'safe':
                checkpoint = CHECKPOINTS.get(key)
                if checkpoint is None:
                    raise ValueError('Unknown canonical checkpoint.')
                self._place(conn, checkpoint['map'])
                if not self._has(trainer,run,checkpoint['requires']):
                    raise ValueError('This save lineage has not reported its prerequisite.')
                if checkpoint['completed'] and self._has(trainer,run,checkpoint['completed']):
                    raise ValueError('This canonical beat is already complete.')
                old = self.db.execute('SELECT document FROM core_story_offers WHERE trainer=? AND run=? AND checkpoint=?',
                                      (trainer,run,key)).fetchone()
                if old:
                    return json.loads(old[0])
                # Query the full committed log, not an LLM summary or a tail
                # window. Private receipts and unrelated side stories never match.
                rows = self.db.execute("SELECT events.seq,events.data FROM events JOIN core_story_shared ON events.seq=core_story_shared.seq WHERE events.kind='world_memory' ORDER BY events.seq")
                evidence=[]
                for seq, raw in rows:
                    event=json.loads(raw)
                    if (event.get('event')=='canonical_story_outcome' and event.get('arc')=='devon_aqua_v1'
                            and event.get('outcome')==checkpoint['outcome']
                            and event.get('source')=='explicitly_shared_native_attestation'):
                        evidence=[seq]
                        break
                through=self.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
                result=dict(schema=1, world_id=self.s.memory.world_id, run=run,
                            checkpoint=key, revision='devon_aqua_v1', through=through,
                            evidence=evidence, branch='warned' if evidence else 'baseline',
                            briefing=checkpoint['changed'] if evidence else checkpoint['baseline'],
                            objective=checkpoint['objective'], effects=['supplemental_briefing','objective_hint'])
                result['digest']=hashlib.sha256(encoded(result).encode()).hexdigest()
                self.db.execute('INSERT INTO core_story_offers VALUES(?,?,?,?)',(trainer,run,key,encoded(result)))
                return result
            raise ValueError('Invalid canonical story action or confirmation.')
