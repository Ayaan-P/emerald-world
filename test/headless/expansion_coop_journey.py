"""Drive a real tagged grass encounter using only native button inputs.

Uses the existing disposable Expansion fixture unchanged; never decodes or
rewrites a Pokemon/save structure with legacy GBA offsets.
"""
import sys
import time


def run(clients, observe, record, report, healthy, press_all, root):
    sys.path.insert(0, str(root / 'test/headless'))
    import maps
    overall = time.monotonic() + 420
    report['scope'] = ('real two-client tagged wild encounter from walking; '
                       'native co-op entry and field return only; '
                       'no capture, medicine, reward ownership or save/reload acceptance')

    def phase(state):
        return state.get('activity', {}).get('phase')

    def free(state):
        return state.get('overworld') and not any(state.get(k) for k in
                    ('locked', 'script', 'battle', 'fade', 'moving'))

    def states():
        healthy()
        if time.monotonic() > overall:
            raise TimeoutError('420-second tagged encounter deadline')
        return observe()

    def wait(label, predicate, seconds=40):
        deadline = min(overall, time.monotonic() + seconds)
        while time.monotonic() < deadline:
            current = states()
            if predicate(current):
                record(label, current)
                report['milestones'].append(label)
                return current
            time.sleep(.1)
        record('timeout: ' + label, states())
        raise TimeoutError(label)

    def tap(name, buttons):
        clients[name].press(buttons, 2)
        clients[name].press([], 12)

    def walk(name, goal, encounter=False):
        deadline = min(overall, time.monotonic() + 35)
        blocked = set()
        failures = 0
        while time.monotonic() < deadline:
            state = states()[name]
            if encounter and (state.get('battle') or
                (state.get('activity', {}).get('mode') == 4 and phase(state) != 'idle')):
                return True
            if state.get('battle'):
                raise RuntimeError('unexpected unshared encounter while routing ' + name)
            if not free(state):
                clients[name].press([], 12)
                continue
            old = tuple(state['pos'])
            if old == goal:
                return False
            level = maps.load(maps.map_name(*state['map']))
            path = level.path(old, goal, blocked, grass_cost=20)
            if not path:
                raise RuntimeError('no native walking path: ' + str((name, old, goal)))
            direction = path[0]
            clients[name].press([direction], 8)
            clients[name].press([], 8)
            after = states()[name]
            if after['map'] != state['map']:
                return False
            if tuple(after['pos']) == old:
                failures += 1
                if failures >= 5:
                    dx, dy = maps.DIRECTIONS[direction]
                    blocked.add((old[0] + dx, old[1] + dy))
                    failures = 0
            else:
                failures = 0
        raise TimeoutError('walking ' + str((name, goal)))

    tap('alice', ['RIGHT'])
    tap('alice', ['A'])
    wait('real tag peer menu opened', lambda s: phase(s['alice']) == 'menu')
    for _ in range(4):
        tap('alice', ['DOWN'])
    tap('alice', ['A'])
    wait('real tag invitation received', lambda s: phase(s['bob']) == 'invitation')
    tap('bob', ['UP'])
    tap('bob', ['A'])
    wait('tag consent returned both trainers to field',
         lambda s: all(free(v) and phase(v) == 'idle' for v in s.values()))
    record('tag consent statuses', states())
    for name, door, destination in (('alice', (6, 12), (8, 18)),
                                    ('bob', (7, 12), (9, 18))):
        walk(name, door)
        origin = states()[name]['map']
        for _ in range(6):
            clients[name].press(['DOWN'], 16)
            if states()[name]['map'] != origin:
                break
        wait('left actual lab ' + name, lambda s, n=name:
             free(s[n]) and maps.map_name(*s[n]['map']) == 'LittlerootTown')
        walk(name, destination)
    for name, x in (('alice', 10), ('bob', 11)):
        walk(name, (x, 0))
        origin = states()[name]['map']
        for _ in range(6):
            clients[name].press(['UP'], 16)
            if states()[name]['map'] != origin:
                break
        wait('walked into Route101 ' + name, lambda s, n=name:
             free(s[n]) and maps.map_name(*s[n]['map']) == 'Route101')
    for name, goal in (('alice', (10, 17)), ('bob', (11, 17)),
                       ('alice', (6, 17)), ('bob', (7, 17))):
        walk(name, goal)
    record('tagged pair before grass', states())
    encountered = False
    for _ in range(25):
        for goal in ((4, 17), (3, 17), (4, 17), (5, 17)):
            if walk('alice', goal, encounter=True):
                encountered = True
                break
        if encountered:
            break
    if not encountered:
        raise RuntimeError('no genuine grass encounter')
    current = states()
    if phase(current['bob']) == 'invitation':
        tap('bob', ['UP'])
        tap('bob', ['A'])
    wait('both native clients entered tagged wild battle', lambda s:
         all(v.get('battle') and v.get('activity', {}).get('mode') == 4
             and phase(v) == 'native' for v in s.values()), 45)
    deadline = min(overall, time.monotonic() + 210)
    iterations = 0
    while time.monotonic() < deadline:
        current = states()
        if iterations % 10 == 0:
            record('co-op controller progress', current)
        iterations += 1
        if all(free(v) and phase(v) == 'idle' for v in current.values()):
            record('both clients returned after tagged wild battle', current)
            report['milestones'].append('both clients returned after tagged wild battle')
            return
        press_all(['A'], 1)
        press_all([], 24)
    record('tagged battle did not complete', states())
    raise TimeoutError('tagged wild battle field return')
