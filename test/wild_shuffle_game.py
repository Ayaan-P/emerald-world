"""Exercise WORLD > Wild shuffle and a real Route 101 encounter offline."""
import driver
from driver import GameError, continue_game, leave_map, wait_until, walk_to

class FoundBattle(Exception):
    pass

def play(game):
    continue_game(game)  # Disposable first-battle save in Birch's lab.
    if game.state.wild_shuffle != {'enabled':False,'seed':1}:
        raise GameError('shuffle was not off by default')
    game.tap('START');game.wait(30);game.tap('DOWN',5);game.tap('A');game.wait(60)
    # WORLD menu defaults to Story; Wild shuffle is immediately above it.
    game.tap('UP');game.tap('A');game.wait(20)
    game.tap('A');game.wait(10)  # Enable seed 1.
    if game.state.wild_shuffle != {'enabled':True,'seed':1}:
        raise GameError('WORLD menu did not enable shuffle')
    game.tap('DOWN');game.tap('A');game.wait(10)  # Seed 2.
    if game.state.wild_shuffle != {'enabled':True,'seed':2}:
        raise GameError('WORLD menu did not select seed 2')
    game.tap('B');game.tap('B');wait_until(game,lambda s:s.free)
    walk_to(game,6,11);leave_map(game,'DOWN')
    walk_to(game,11,0);leave_map(game,'UP')
    if game.state.map_name!='Route101':raise GameError('not on Route 101')
    def see_battle(g):
        def opponent(s):
            return bool(s.battle_state and any(b.get('side')==1 for b in s.battle_state.get('battlers',[])))
        wait_until(g,opponent,step=10,limit=4000)
        enemies=[b['species'] for b in g.state.battle_state['battlers'] if b.get('side')==1]
        # Seed 2 maps Route 101's original National Dex entries 261,263,265
        # to 207,43,243 respectively, which have identical native IDs here.
        if not enemies or any(n not in (207,43,243) for n in enemies):
            raise GameError('wild encounter did not use seed-2 mapping: '+repr(enemies))
        raise FoundBattle()
    # Approach on ordinary ground, then step into and out of grass directly.
    # Do not use walk_to's default battle handler: the shuffled encounter may
    # be a legendary that the disposable starter cannot defeat.
    driver.fight_battle=see_battle  # Also intercept battles that begin during a field transition.
    try:
        walk_to(game,10,10,on_battle=see_battle)
        for i in range(100):
            game.press('RIGHT' if i % 2 == 0 else 'LEFT',16)
            wait_until(game,lambda state:state.battle or state.free,step=2,limit=1200)
            if game.state.battle: see_battle(game)
    except FoundBattle:
        return
    raise GameError('no Route 101 encounter while walking in grass')
