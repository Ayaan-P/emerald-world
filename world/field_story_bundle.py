"""Reviewed, atomic installation of an authored mystery and its consequences."""
import copy
from .cooperative_mysteries import validate as validate_mystery, dump
from .opportunities import validate as validate_story

# Kept in a Python module so ordinary source and packaged launchers include it.
CURATED = {'mystery': {'id': 'signal_v2',
             'title': 'The Two-Tower Signal',
             'roles': ['Field Observer', 'Archive Decoder'],
             'ending': 'Together you decoded the old route signal. Your expedition is recorded.',
             'stages': [{'title': 'The missing word',
                         'stations': [{'at': [0, 0, 10, 10],
                                       'clue': 'The weather vane shows a SUN. Tell the decoder exactly what '
                                               'you see.'},
                                      {'at': [0, 0, 22, 12],
                                       'clue': 'Archive rule: append RISE to the observers symbol. Submit '
                                               'the joined word.'}],
                         'answer': 'SUNRISE',
                         'result': 'The first signal is decoded. Follow the second pair of stations.'},
                        {'title': 'The second beacon',
                         'stations': [{'at': [0, 3, 10, 40],
                                       'clue': 'The beacon flashes BLUE. Tell your partner its color.'},
                                      {'at': [0, 3, 22, 40],
                                       'clue': 'The ledger pairs BLUE with TIDE and RED with ASH. Submit the '
                                               'matching word.'}],
                         'answer': 'TIDE',
                         'result': 'The towers answer in harmony. The old message is complete.'}]},
 'story': {'id': 'signal_after_v2',
           'title': 'The River Signal Returns',
           'qualities': {'relay': {'scope': 'place', 'initial': 0, 'max': 2},
                         'heard': {'scope': 'player', 'initial': 0, 'max': 1}},
           'scenes': {'decision': {'place': 'RustboroCity',
                                   'text': 'Your decoded signal reveals an old flood warning relay. What '
                                           'should the town do?',
                                   'requires': {'relay': [0, 0]},
                                   'once': 'world',
                                   'mystery': 'signal_v2',
                                   'choices': {'restore': {'text': 'Restore the public warning relay.',
                                                           'requires': {},
                                                           'effects': {'relay': 1},
                                                           'result': 'The town adopts the warning signal. '
                                                                     'Later visitors will hear its story.'},
                                               'archive': {'text': 'Preserve the message in the town '
                                                                   'archive.',
                                                           'requires': {},
                                                           'effects': {'relay': 2},
                                                           'result': 'The town preserves the decoded '
                                                                     'message. Later visitors can learn its '
                                                                     'history.'}}},
                      'warning': {'place': 'RustboroCity',
                                  'text': 'Townspeople tell you two explorers recovered the river warning '
                                          'signal.',
                                  'requires': {'relay': [1, 1], 'heard': [0, 0]},
                                  'once': 'player',
                                  'choices': {'listen': {'text': 'Learn the warning call.',
                                                         'requires': {},
                                                         'effects': {'heard': 1},
                                                         'result': 'You remember the story of the restored '
                                                                   'relay.'}}},
                      'archive': {'place': 'RustboroCity',
                                  'text': 'The archive displays an old river message recovered by two '
                                          'explorers.',
                                  'requires': {'relay': [2, 2], 'heard': [0, 0]},
                                  'once': 'player',
                                  'choices': {'read': {'text': 'Read the recovered message.',
                                                       'requires': {},
                                                       'effects': {'heard': 1},
                                                       'result': 'You remember the story of the archived '
                                                                 'signal.'}}}}}}


def curated():
    return copy.deepcopy(CURATED)


def inspect(server, bundle):
    if type(bundle) is not dict or set(bundle) != {'mystery','story'}:
        raise ValueError('Choose one mystery and its follow-up story.')
    mystery, story = bundle['mystery'], bundle['story']
    validate_mystery(mystery, server.mysteries.coords)
    validate_story(story, server.opportunities.places)
    for stage in mystery['stages']:
        if any(tuple(station['at'][:2]) in (server.cave_map,server.wilds_map) for station in stage['stations']):
            raise ValueError('Mysteries require stable standard maps.')
    if not any(scene.get('mystery') == mystery['id'] for scene in story['scenes'].values()):
        raise ValueError('The follow-up story must use this mystery completion.')
    for scene in story['scenes'].values():
        prerequisite = scene.get('mystery')
        if prerequisite and prerequisite != mystery['id']:
            server.mysteries._pack(prerequisite)
    existing=[]
    for table,pack in [('mystery_packs',mystery),('story_packs',story)]:
        row=server.db.execute('SELECT document FROM '+table+' WHERE id=?',(pack['id'],)).fetchone()
        if row and row[0]!=dump(pack):raise ValueError('Existing content uses this identity differently. Nothing was replaced.')
        if not row and server.db.execute('SELECT count(*) FROM '+table).fetchone()[0]>=64:
            raise ValueError('World story capacity reached.')
        existing.append(bool(row))
    return dict(mystery=mystery['id'],story=story['id'],title=mystery['title'],players=2,
                stages=len(mystery['stages']),installed=all(existing),
                stations=[dict(stage=i+1,role=mystery['roles'][role],map=server.mysteries.coords(*station['at'])['name'],
                               x=station['at'][2],y=station['at'][3])
                          for i,stage in enumerate(mystery['stages']) for role,station in enumerate(stage['stations'])])


def install(server,bundle):
    with server.db:
        report=inspect(server,bundle)
        for table,key in [('mystery_packs','mystery'),('story_packs','story')]:
            pack=bundle[key]
            server.db.execute('INSERT OR IGNORE INTO '+table+' VALUES(?,?)',(pack['id'],dump(pack)))
        result=inspect(server,bundle)
        if not result['installed']:raise ValueError('The complete field story was not saved.')
    return dict(ok=True,**result)
