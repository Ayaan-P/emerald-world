"""Versioned, world-owned settings. Values are inert data, never code."""
import json

DEFAULT_RULES = {'wild_shuffle': {'enabled': False, 'seed': 1}}


def validate_rules(value):
    if type(value) is not dict or set(value) != {'wild_shuffle'}:
        raise ValueError('expected wild_shuffle rule')
    shuffle = value['wild_shuffle']
    if (type(shuffle) is not dict or set(shuffle) != {'enabled', 'seed'}
            or type(shuffle['enabled']) is not bool or type(shuffle['seed']) is not int
            or not 1 <= shuffle['seed'] <= 20):
        raise ValueError('wild_shuffle needs enabled (boolean) and seed (1-20)')
    return {'wild_shuffle': {'enabled': shuffle['enabled'], 'seed': shuffle['seed']}}


class WorldRules:
    def __init__(self, database):
        self.db = database
        self.db.execute('''CREATE TABLE IF NOT EXISTS world_rules (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            revision INTEGER NOT NULL, value TEXT NOT NULL)''')
        self.db.execute('INSERT OR IGNORE INTO world_rules VALUES (1, 0, ?)',
                        (json.dumps(DEFAULT_RULES, sort_keys=True, separators=(',', ':')),))
        self.db.commit()
        self.status()  # Refuse invalid persisted rules rather than silently changing a world.

    def status(self):
        row = self.db.execute('SELECT revision, value FROM world_rules WHERE singleton=1').fetchone()
        if not row or type(row[0]) is not int or not 0 <= row[0] <= 2147483647:
            raise ValueError('invalid world rules revision')
        try:
            rules = validate_rules(json.loads(row[1]))
        except (ValueError, TypeError) as exc:
            raise ValueError('invalid stored world rules') from exc
        return {'ok': True, 'version': 1, 'revision': row[0], 'rules': rules}

    def replace(self, value, expected_revision):
        rules = validate_rules(value)
        if type(expected_revision) is not int or not 0 <= expected_revision < 2147483647:
            raise ValueError('expected_revision must be a valid revision')
        encoded = json.dumps(rules, sort_keys=True, separators=(',', ':'))
        with self.db:
            changed = self.db.execute('UPDATE world_rules SET revision=revision+1, value=? '
                                      'WHERE singleton=1 AND revision=?', (encoded, expected_revision))
            if changed.rowcount != 1:
                raise ValueError('world rules changed; refresh and retry')
        return self.status()

    def line(self):
        state = self.status()
        rule = state['rules']['wild_shuffle']
        return f'RULES 1 {state["revision"]} {int(rule["enabled"])} {rule["seed"]}\n'

    def requires_capability(self):
        return self.status()['rules']['wild_shuffle']['enabled']
