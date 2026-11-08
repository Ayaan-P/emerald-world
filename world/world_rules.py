"""Versioned, world-owned settings. Values are inert data, never code."""
import json

V2_GAMEPLAY_BITS = {'reusable_tms': 1, 'evolution_items_from_bag': 2, 'party_exp_share': 4}
# Permissions only: battle mechanics remain solo-only until controller/owner
# contracts exist. Dynamax does not grant a Gigantamax factor or eligibility.
GAMEPLAY_BITS = {**V2_GAMEPLAY_BITS, 'mega_primal': 8, 'z_moves': 16,
                 'dynamax': 32, 'terastallization': 64,
                 'expanded_species_pool': 128, 'pokemon_follower': 256}
DEFAULT_RULES = {'wild_shuffle': {'enabled': False, 'seed': 1},
                 **dict.fromkeys(GAMEPLAY_BITS, False)}


def validate_rules(value):
    # V1/V2 storage is adapted on read only. Unknown or partial documents
    # are never treated as defaults.
    if type(value) is not dict or set(value) not in ({'wild_shuffle'}, {'wild_shuffle', *V2_GAMEPLAY_BITS}, set(DEFAULT_RULES)):
        raise ValueError('expected complete world rules')
    gameplay = {key: value.get(key, False) for key in GAMEPLAY_BITS}
    if any(type(flag) is not bool for flag in gameplay.values()):
        raise ValueError('gameplay rules must be booleans')
    shuffle = value['wild_shuffle']
    if (type(shuffle) is not dict or set(shuffle) != {'enabled', 'seed'}
            or type(shuffle['enabled']) is not bool or type(shuffle['seed']) is not int
            or not 1 <= shuffle['seed'] <= 20):
        raise ValueError('wild_shuffle needs enabled (boolean) and seed (1-20)')
    return {'wild_shuffle': {'enabled': shuffle['enabled'], 'seed': shuffle['seed']}, **gameplay}


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
        return {'ok': True, 'version': 3, 'revision': row[0], 'rules': rules}

    def replace(self, value, expected_revision):
        rules = validate_rules(value)
        current = self.status()['rules']
        if any(current[key] and key not in value for key in GAMEPLAY_BITS):
            raise ValueError('complete world rules required; refresh and retry')
        if type(expected_revision) is not int or not 0 <= expected_revision < 2147483647:
            raise ValueError('expected_revision must be a valid revision')
        encoded = json.dumps(rules, sort_keys=True, separators=(',', ':'))
        with self.db:
            changed = self.db.execute('UPDATE world_rules SET revision=revision+1, value=? '
                                      'WHERE singleton=1 AND revision=?', (encoded, expected_revision))
            if changed.rowcount != 1:
                raise ValueError('world rules changed; refresh and retry')
        return self.status()

    @staticmethod
    def gameplay_mask(rules):
        return sum(bit for key, bit in GAMEPLAY_BITS.items() if rules[key])

    def line(self, version=1):
        state = self.status()
        rule = state['rules']['wild_shuffle']
        mask = self.gameplay_mask(state['rules'])
        if version == 1 and mask == 0:
            return f'RULES 1 {state["revision"]} {int(rule["enabled"])} {rule["seed"]}\n'
        if version in (2, 3) and (version == 3 or mask <= 7):
            return f'RULES {version} {state["revision"]} {int(rule["enabled"])} {rule["seed"]} {mask}\n'
        raise ValueError('unsupported world rules capability')

    def requires_capability(self, version=0):
        rules = self.status()['rules']
        mask = self.gameplay_mask(rules)
        return ((mask > 7 and version < 3)
                or (mask != 0 and version < 2)
                or (rules['wild_shuffle']['enabled'] and version < 1))
