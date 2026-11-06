#!/usr/bin/env python3
"""Port an audited effect-equivalent subset from the pinned donor, never its layouts.
Gen 6-9 numerical tuning is selected explicitly (not later Champions tuning).
No unsupported donor effect receives an ID or a playable data row.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN = 'bb3fd057061cdd7e6a9e79b76abb41924ee44ecc'
# Native script equivalences are explicit, not a fallback for unknown effects.
PORTS = [
 ('MOONBLAST','SPECIAL_ATTACK_DOWN_HIT',30,'PSYCHIC'),
 ('DAZZLING_GLEAM','HIT',0,'SWIFT'),
 ('FAIRY_WIND','HIT',0,'SILVER_WIND'),
 ('PLAY_ROUGH','ATTACK_DOWN_HIT',10,'DIZZY_PUNCH'),
 ('AURA_SPHERE','ALWAYS_HIT',0,'SHOCK_WAVE'),
 ('DARK_PULSE','FLINCH_HIT',20,'SHADOW_BALL'),
 ('AIR_SLASH','FLINCH_HIT',30,'AIR_CUTTER'),
 ('FLASH_CANNON','SPECIAL_DEFENSE_DOWN_HIT',10,'LUSTER_PURGE'),
 ('DRAGON_PULSE','HIT',0,'DRAGON_BREATH'),
 ('NASTY_PLOT','SPECIAL_ATTACK_UP_2',0,'TAIL_GLOW'),
 ('AQUA_JET','HIT',0,'QUICK_ATTACK'),
 ('BULLET_PUNCH','HIT',0,'MACH_PUNCH'),
 ('ICE_SHARD','HIT',0,'ICE_BEAM'),
 ('SHADOW_SNEAK','HIT',0,'SHADOW_PUNCH'),
 ('ZEN_HEADBUTT','FLINCH_HIT',20,'HEADBUTT'),
 ('IRON_HEAD','FLINCH_HIT',30,'HEADBUTT'),
 ('X_SCISSOR','HIT',0,'SLASH'),
 ('SEED_BOMB','HIT',0,'BULLET_SEED'),
 ('ENERGY_BALL','SPECIAL_DEFENSE_DOWN_HIT',10,'SHADOW_BALL'),
 ('EARTH_POWER','SPECIAL_DEFENSE_DOWN_HIT',10,'EARTHQUAKE'),
 ('POWER_GEM','HIT',0,'ANCIENT_POWER'),
 ('VACUUM_WAVE','HIT',0,'MACH_PUNCH'),
 ('PSYCHO_CUT','HIGH_CRITICAL',0,'SLASH'),
 ('NIGHT_SLASH','HIGH_CRITICAL',0,'SLASH'),
 ('LEAF_STORM','OVERHEAT',0,'RAZOR_LEAF'),
 ('DRACO_METEOR','OVERHEAT',0,'DRAGON_BREATH'),
 ('BRAVE_BIRD','DOUBLE_EDGE',0,'WING_ATTACK'),
 ('WOOD_HAMMER','DOUBLE_EDGE',0,'DOUBLE_EDGE'),
 ('GIGA_IMPACT','RECHARGE',0,'HYPER_BEAM'),
 ('SLUDGE_WAVE','POISON_HIT',10,'SLUDGE_BOMB'),
 ('ICICLE_CRASH','FLINCH_HIT',30,'ICE_BEAM'),
 ('PETAL_BLIZZARD','HIT',0,'RAZOR_LEAF'),
 ('SMART_STRIKE','ALWAYS_HIT',0,'HORN_ATTACK'),
 ('SPIRIT_BREAK','SPECIAL_ATTACK_DOWN_HIT',100,'BRICK_BREAK'),
 ('FORCE_PALM','PARALYZE_HIT',30,'ARM_THRUST'),
 ('DRAGON_RUSH','FLINCH_MINIMIZE_HIT',20,'DRAGON_CLAW'),
 ('ROCK_POLISH','SPEED_UP_2',0,'AGILITY'),
 ('DOUBLE_HIT','DOUBLE_HIT',0,'DOUBLE_KICK'),
 ('ROCK_WRECKER','RECHARGE',0,'ROCK_SLIDE'),
 ('POISON_JAB','POISON_HIT',30,'POISON_STING'),
 ('CROSS_POISON','POISON_TAIL',10,'POISON_TAIL'),
 ('DRAIN_PUNCH','ABSORB',0,'MEGA_DRAIN'),
 ('HORN_LEECH','ABSORB',0,'GIGA_DRAIN'),
 ('STONE_EDGE','HIGH_CRITICAL',0,'ROCK_SLIDE'),
 ('LIQUIDATION','DEFENSE_DOWN_HIT',20,'WATERFALL'),
 ('LUNGE','ATTACK_DOWN_HIT',100,'LEECH_LIFE'),
 ('SKITTER_SMACK','SPECIAL_ATTACK_DOWN_HIT',100,'LEECH_LIFE'),
 ('MYSTICAL_FIRE','SPECIAL_ATTACK_DOWN_HIT',100,'FLAMETHROWER'),
 ('HIGH_HORSEPOWER','HIT',0,'STOMP'),
 ('WILD_CHARGE','RECOIL',0,'TAKE_DOWN'),
 ('ACCELEROCK','HIT',0,'QUICK_ATTACK'),
 ('CLOSE_COMBAT','DEF_SPDEF_DOWN_HIT',0,'SUPERPOWER'),
 ('HEADLONG_RUSH','DEF_SPDEF_DOWN_HIT',0,'TAKE_DOWN'),
 ('HAMMER_ARM','SELF_SPEED_DOWN_HIT',0,'MEGA_PUNCH'),
 ('ICE_HAMMER','SELF_SPEED_DOWN_HIT',0,'ICE_PUNCH'),
]
# Serialized IDs are permanent assignments, never derived from PORTS order.
ASSIGNED_IDS = {
    'MOVE_STONE_EDGE': 398,
    'MOVE_LIQUIDATION': 399,
    'MOVE_LUNGE': 400,
    'MOVE_SKITTER_SMACK': 401,
    'MOVE_MYSTICAL_FIRE': 402,
    'MOVE_HIGH_HORSEPOWER': 403,
    'MOVE_WILD_CHARGE': 404,
    'MOVE_ACCELEROCK': 405,
    'MOVE_CLOSE_COMBAT': 406,
    'MOVE_HEADLONG_RUSH': 407,
    'MOVE_HAMMER_ARM': 408,
    'MOVE_ICE_HAMMER': 409,
}
OVERRIDES = {'AURA_SPHERE':{'power':'80'},'AIR_SLASH':{'pp':'15'},
 'DRAGON_PULSE':{'power':'85'},'ENERGY_BALL':{'power':'90'},
 'POWER_GEM':{'power':'80'},'LEAF_STORM':{'power':'130'},
 'DRACO_METEOR':{'power':'130'},'NIGHT_SLASH':{'pp':'15'},
 'DRAIN_PUNCH':{'power':'75','pp':'10'}, 'MYSTICAL_FIRE':{'power':'75'},
 'HEADLONG_RUSH':{'power':'120'}}
SHORT_DISPLAYS = {'HEADLONG_RUSH': 'HEADLNG RUSH'}
ALIASES = {'VISE_GRIP':'VICE_GRIP','HIGH_JUMP_KICK':'HI_JUMP_KICK',
 'FEINT_ATTACK':'FAINT_ATTACK','SMELLING_SALTS':'SMELLING_SALT'}

def field(body, name):
    m = re.search(r'^\s*\.'+name+r' = ([^,\n]+)', body, re.M)
    if not m:
        raise ValueError(name)
    return m[1]

def insert(path, text, marker='\n};', root=ROOT):
    p = root/path
    s = p.read_text()
    # Includes are idempotent and leave all native entries byte-for-byte intact.
    if text.strip() not in s:
        i = s.rindex(marker)
        p.write_text(s[:i]+'\n'+text+s[i:])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--donor',type=Path,required=True)
    ap.add_argument('--output', type=Path, help='Disposable repository-shaped staging root')
    args=ap.parse_args()
    destination = args.output.resolve() if args.output else ROOT
    if args.output and (destination == ROOT or ROOT not in destination.parents):
        raise SystemExit('Staging output must be a separate directory inside this checkout')
    seed = json.loads((ROOT/'tools/expanded_moves/coverage.json').read_text())
    legacy = seed['effect_supported']
    target_ids = {name: int(value) for name, value in re.findall(
        r'^#define (MOVE_\w+) (\d+)$', (ROOT/'include/constants/moves.h').read_text(), re.M)}
    if seed['donor_pin'] != PIN or seed['move_count'] != 355+len(legacy):
        raise ValueError('Legacy manifest provenance or count mismatch')
    if any(target_ids.get(row['name']) != row['native_id'] for row in legacy):
        raise ValueError('Legacy manifest IDs disagree with target constants')
    if any(target_ids.get('MOVE_'+name, 355) < 355 for name, *_ in PORTS):
        raise ValueError('Port would duplicate an existing native move')
    by_name = {'MOVE_'+p[0]: p for p in PORTS}
    if len(by_name) != len(PORTS):
        raise ValueError('Duplicate port name')
    if [r['native_id'] for r in legacy] != list(range(355, 355+len(legacy))):
        raise ValueError('Non-contiguous legacy ID prefix')
    assigned_ids = {r['name']: r['native_id'] for r in legacy}
    if len(assigned_ids) != len(legacy):
        raise ValueError('Duplicate legacy name')
    if any(name in assigned_ids and assigned_ids[name] != native_id
           for name, native_id in ASSIGNED_IDS.items()):
        raise ValueError('Stable assignments disagree with legacy seed')
    assigned_ids.update(ASSIGNED_IDS)
    if set(assigned_ids) != set(by_name):
        raise ValueError('Ports and stable assignments disagree')
    if sorted(assigned_ids.values()) != list(range(355, 355+len(assigned_ids))):
        raise ValueError('Stable assignment collision or gap')
    if any(name in target_ids and target_ids[name] != native_id
           for name, native_id in assigned_ids.items()):
        raise ValueError('Stable assignments disagree with target constants')
    if any(native_id in assigned_ids.values() and assigned_ids.get(name) != native_id
           for name, native_id in target_ids.items()):
        raise ValueError('Stable assignment collides with target constants')
    ports = [by_name[name] for name in sorted(assigned_ids, key=lambda name: assigned_ids[name])]
    if 355+len(ports) > 512:
        raise ValueError('Moves exceed native 9-bit learnset capacity')
    # Seed all integration files from the target, not a donor layout or a stale stage.
    integration = ['include/constants/moves.h', 'src/data/battle_moves.h',
                   'src/data/text/move_names.h', 'src/data/contest_moves.h',
                   'src/data/text/move_descriptions.h', 'data/battle_anim_scripts.s']
    if destination != ROOT:
        for relative in integration:
            target = destination/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/relative).read_bytes())
    actual=subprocess.check_output(['git','-C',str(args.donor),'rev-parse','HEAD'],text=True).strip()
    if actual != PIN:
        raise SystemExit('Donor pin mismatch: '+actual)
    donor=(args.donor/'src/data/moves_info.h').read_text()
    entries=dict(re.findall(r'\[(MOVE_\w+)\] =\s*\{(.*?)\n    \},',donor,re.S))
    output=destination/'src/data/expanded_moves'
    output.mkdir(parents=True,exist_ok=True)
    rows=[]; names=[]; descriptions=[]; pointers=[]; categories=[]; contests=[]; animations=[]; manifest=[]
    for offset,(name,effect,chance,anim) in enumerate(ports):
        key='MOVE_'+name
        body=entries[key]
        values={f:OVERRIDES.get(name,{}).get(f) or field(body,f) for f in ['power','type','accuracy','pp','priority','target','category']}
        if any('?' in v for v in values.values()):
            raise ValueError((name,values))
        target=values['target'].replace('TARGET_','MOVE_TARGET_').replace('MOVE_TARGET_FOES_AND_ALLY','MOVE_TARGET_FOES_AND_ALLY')
        cat=values['category'].replace('DAMAGE_CATEGORY_','EXPANDED_CATEGORY_')
        flags=[]
        if '.makesContact = TRUE' in body: flags.append('FLAG_MAKES_CONTACT')
        if '.ignoresProtect = TRUE' not in body: flags.append('FLAG_PROTECT_AFFECTED')
        if '.mirrorMoveBanned = TRUE' not in body: flags.append('FLAG_MIRROR_MOVE_AFFECTED')
        if '.snatchAffected = TRUE' in body: flags.append('FLAG_SNATCH_AFFECTED')
        if values['power'] != '0' and not chance: flags.append('FLAG_KINGS_ROCK_AFFECTED')
        rows.append(f'    [{key}] = {{ .effect = EFFECT_{effect}, .power = {values["power"]}, .type = {values["type"]}, .accuracy = {values["accuracy"]}, .pp = {values["pp"]}, .secondaryEffectChance = {chance}, .target = {target}, .priority = {values["priority"]}, .flags = '+(' | '.join(flags) or '0')+' },')
        display=field(body,'name')
        display=SHORT_DISPLAYS.get(name, re.search(r'"([^"]+)"',display)[1].upper())
        if len(display)>12:
            display={'DAZZLING GLEAM':'DAZZL.GLEAM','PETAL BLIZZARD':'PETAL BLIZ.', 'MYSTICAL FIRE':'MYSTIC.FIRE', 'HIGH HORSEPOWER':'HIGH HORSEPW', 'SKITTER SMACK':'SKITTR SMACK'}[display]
        names.append(f'    [{key}] = _("{display}"),')
        desc=re.search(r'\.description = COMPOUND_STRING\((.*?)\),',body,re.S)[1]
        if '#' in desc:
            desc='"Powerful, but leaves the\\n"\n    "user immobile the next turn."'
        descriptions.append(f'static const u8 sExpanded{name}Description[] = _(\n    {desc.strip()});')
        pointers.append(f'    [{key} - 1] = sExpanded{name}Description,')
        categories.append(f'    [{key} - EXPANDED_MOVES_START] = {cat},')
        ce=field(body,'contestEffect')
        # Omitted donor field is zero-initialized (COOL), not a guessed category.
        cc='CONTEST_CATEGORY_COOL' if name == 'HEADLONG_RUSH' else field(body,'contestCategory')
        if '?' in cc: cc=cc.split('?')[1].split(':')[0].strip()
        if '?' in ce: ce=ce.split('?')[1].split(':')[0].strip()
        ce = {'CONTEST_EFFECT_APPEAL_AS_GOOD_AS_PREV_ONE':'CONTEST_EFFECT_APPEAL_AS_GOOD_AS_PREV_ONES'}.get(ce,ce)
        contests.append(f'    [{key}] = {{ .effect = {ce}, .contestCategory = {cc} }},')
        animations.append('\tptrvalue Move_'+anim)
        manifest.append(dict(name=key,native_id=355+offset,donor_effect=field(body,'effect'),effect='EFFECT_'+effect,category=cat,secondary_chance=chance,animation_reuse='Move_'+anim,effect_supported=True))
    for filename,lines in [('battle_moves.h',rows),('names.h',names),('descriptions.h',descriptions),('description_pointers.h',pointers),('categories.h',categories),('contest_moves.h',contests)]:
        (output/filename).write_text((ROOT/'src/data/expanded_moves'/filename).read_text()+'\n'.join(lines[len(legacy):])+('\n' if len(ports)>len(legacy) else ''))
    (destination/'data/expanded_move_animations.inc').write_text((ROOT/'data/expanded_move_animations.inc').read_text()+'\n'.join(animations[len(legacy):])+('\n' if len(ports)>len(legacy) else ''))
    p=destination/'include/constants/moves.h';s=p.read_text()
    block='#ifdef PORTABLE\n/* Native IDs 0..354 remain unchanged. Donor numeric IDs are never serialized. */\n'
    block+='\n'.join(f'#define MOVE_{n} {355+i}' for i,(n,*_) in enumerate(ports))
    block+='\n'+ '\n'.join(f'#define MOVE_{a} MOVE_{n}' for a,n in ALIASES.items())
    block+=f'\n#define MOVES_COUNT {355+len(ports)}\n#else\n#define MOVES_COUNT 355\n#endif'
    if '#define MOVE_MOONBLAST ' not in s:
        p.write_text(s.replace('#define MOVES_COUNT 355',block))
    else:
        s = re.sub(r'#ifdef PORTABLE\n/\* Native IDs 0\.\.354.*?\n#endif',lambda _:block,s,count=1,flags=re.S)
        p.write_text(s)
    insert('src/data/battle_moves.h','#ifdef PORTABLE\n#include "expanded_moves/battle_moves.h"\n#endif', root=destination)
    insert('src/data/text/move_names.h','#ifdef PORTABLE\n#include "../expanded_moves/names.h"\n#endif', root=destination)
    insert('src/data/contest_moves.h','#ifdef PORTABLE\n#include "expanded_moves/contest_moves.h"\n#endif', marker='\n};\n\nconst struct ContestEffect', root=destination)
    p=destination/'src/data/text/move_descriptions.h';s=p.read_text()
    inc='#ifdef PORTABLE\n#include "../expanded_moves/descriptions.h"\n#endif\n\n'
    if inc not in s: p.write_text(inc+s)
    insert('src/data/text/move_descriptions.h','#ifdef PORTABLE\n#include "../expanded_moves/description_pointers.h"\n#endif', root=destination)
    p=destination/'data/battle_anim_scripts.s';s=p.read_text()
    marker='\tptrvalue Move_PSYCHO_BOOST'
    inc='\n#ifdef PORTABLE\n#include "data/expanded_move_animations.inc"\n#endif'
    if inc not in s: p.write_text(s.replace(marker,marker+inc,1))
    # Translate donor type names, not donor numeric values (TYPE_NONE differs).
    types = ['NORMAL','FIGHTING','FLYING','POISON','GROUND','ROCK','BUG','GHOST',
             'STEEL','MYSTERY','FIRE','WATER','GRASS','ELECTRIC','PSYCHIC','ICE',
             'DRAGON','DARK','FAIRY']
    donor_types = ['NONE'] + types + ['STELLAR']
    type_data = (args.donor/'src/data/types_info.h').read_text().split('const struct TypeInfo')[0]
    multipliers = {'______':10,'STL_RS':10,'PSN_RS':5,'BUG_RS':10,'PSY_RS':20,'FIR_RS':5,
                   'X(0.5)':5,'X(0.0)':0,'X(2.0)':20}
    chart=[]
    for attack in types:
        match=re.search(r'\[TYPE_'+attack+r'\]\s*=\s*\{([^}]+)\}',type_data)
        if match is None: raise ValueError(attack)
        values=[multipliers[v.strip()] for v in match[1].split(',')]
        if len(values)!=len(donor_types): raise ValueError(attack)
        for defense,value in zip(donor_types,values):
            if defense not in types or value==10: continue
            if defense=='GHOST' and attack in ('NORMAL','FIGHTING'): continue
            chart.append(f'    TYPE_{attack}, TYPE_{defense}, {value},')
    chart += ['    TYPE_FORESIGHT, TYPE_FORESIGHT, 0,',
              '    TYPE_NORMAL, TYPE_GHOST, 0,', '    TYPE_FIGHTING, TYPE_GHOST, 0,',
              '    TYPE_ENDTABLE, TYPE_ENDTABLE, 0,']
    (output/'type_chart.h').write_text('/* Donor bb3fd057 modern matchups. Foresight boundary retained. */\n'+'\n'.join(chart)+'\n')
    recognized=sorted(set(entries)-{'MOVE_NONE'})
    native_names = {
        m[0] for m in re.findall(r'^#define (MOVE_\w+) (\d+)$',(ROOT/'include/constants/moves.h').read_text(),re.M) if int(m[1])<=354}
    native_names.update('MOVE_'+a for a in ALIASES)
    coverage={'donor_pin':PIN,'tuning':'Gen 6-9; native engine ability set, critical and recoil rounding retained',
      'native_ids_preserved':[0,354],'move_count':355+len(ports),'effect_supported':manifest,
      'recognized_native_names':sorted(set(recognized)&native_names),
      'recognized_but_not_ported':[n for n in recognized if n not in native_names and n not in {r['name'] for r in manifest}],
      'policy':'Only effect_supported appended IDs may enter new roster learnsets. Unknown donor names must fail, never alias to HIT.'}
    coverage['effect_supported'][:len(legacy)] = legacy
    coverage['candidate_audit'] = {
        'MOVE_ROCK_BLAST': {'status': 'existing_native', 'native_id': 350,
            'reason': 'Already EFFECT_MULTI_HIT. Native 80 accuracy and native multi-hit distribution retained; no duplicate ID or retuning.'},
        'MOVE_SCALD': {'status': 'unsupported',
            'reason': 'Donor thawsUser plus Water-type target thawing require move-specific native support. BURN_HIT alone is not equivalent.'},
        'MOVE_DISCHARGE': {'status': 'unsupported',
            'reason': 'TARGET_FOES_AND_ALLY requires all-other-battler iteration. Native MOVEEND_NEXT_TARGET only iterates MOVE_TARGET_BOTH; PARALYZE_HIT is insufficient.'},
        'MOVE_LAVA_PLUME': {'status': 'unsupported',
            'reason': 'TARGET_FOES_AND_ALLY requires all-other-battler iteration. Native MOVEEND_NEXT_TARGET only iterates MOVE_TARGET_BOTH; BURN_HIT is insufficient.'},
        'MOVE_BREAKING_SWIPE': {'status': 'unsupported',
            'reason': 'TARGET_BOTH and ATTACK_DOWN_HIT are available, but donor metronomeBanned is not represented by native per-move flags or its fixed forbidden list.'},
    }
    for row in manifest[len(legacy):]:
        body = entries[row['name']]
        expected_donor_effect = 'EFFECT_RECOIL' if row['name'] == 'MOVE_WILD_CHARGE' else 'EFFECT_HIT'
        if field(body, 'effect') != expected_donor_effect:
            raise ValueError('Donor effect drift: '+row['name'])
        stat = {'EFFECT_DEFENSE_DOWN_HIT': 'defense', 'EFFECT_ATTACK_DOWN_HIT': 'attack',
                'EFFECT_SPECIAL_ATTACK_DOWN_HIT': 'spAtk'}.get(row['effect'])
        if stat and ('.moveEffect = MOVE_EFFECT_STAT_MINUS' not in body or
                     field(body, stat) != '1'):
            raise ValueError('Donor stat effect mismatch: '+row['name'])
        if row['effect'] == 'EFFECT_HIGH_CRITICAL' and field(body, 'criticalHitStage') != 'B_UPDATED_MOVE_DATA >= GEN_3 ? 1 : 2':
            raise ValueError('Donor critical stage mismatch: '+row['name'])
        if row['effect'] == 'EFFECT_RECOIL' and '.recoilPercentage = 25' not in body:
            raise ValueError('Donor recoil mismatch: '+row['name'])
        if row['effect'] in ('EFFECT_DEF_SPDEF_DOWN_HIT', 'EFFECT_SELF_SPEED_DOWN_HIT'):
            stats = ('defense', 'spDef') if row['effect'] == 'EFFECT_DEF_SPDEF_DOWN_HIT' else ('speed',)
            if ('.moveEffect = MOVE_EFFECT_STAT_MINUS' not in body or '.self = TRUE' not in body
                    or any(field(body, stat) != '1' for stat in stats)
                    or re.search(r'\.chance =', body)):
                raise ValueError('Donor guaranteed self drop mismatch: '+row['name'])
            if row['name'] == 'MOVE_HEADLONG_RUSH' and field(body, 'power') != 'B_UPDATED_MOVE_DATA >= GEN_9 ? 120 : 100':
                raise ValueError('Donor Gen9 power mismatch: '+row['name'])
        if field(body, 'target') != 'TARGET_SELECTED':
            raise ValueError('Unaudited target: '+row['name'])
        if re.search(r'\.(soundMove|thawsUser|ignoresProtect|mirrorMoveBanned|metronomeBanned) = TRUE', body):
            raise ValueError('Unsupported donor flag: '+row['name'])
        if row['animation_reuse']+':' not in (ROOT/'data/battle_anim_scripts.s').read_text():
            raise ValueError('Missing native animation: '+row['name'])
        if row['effect'] not in (ROOT/'include/constants/battle_move_effects.h').read_text():
            raise ValueError('Missing native effect: '+row['name'])
        donor_chance = re.search(r'\.chance = (\d+)', body)
        if (int(donor_chance[1]) if donor_chance else 0) != row['secondary_chance']:
            raise ValueError('Secondary chance mismatch: '+row['name'])
        coverage['candidate_audit'][row['name']] = dict(status='staged_supported',
            native_id=row['native_id'], native_effect=row['effect'],
            secondary_chance=row['secondary_chance'], animation_reuse=row['animation_reuse'],
            donor_source=body.strip(),
            policy='Native Gen3 critical probabilities and quarter-recoil floor/minimum-one rounding retained. Native ability set only.')
        if row['effect'] in ('EFFECT_DEF_SPDEF_DOWN_HIT', 'EFFECT_SELF_SPEED_DOWN_HIT'):
            coverage['candidate_audit'][row['name']].update(
                self_drop_certain=True,
                self_drop_secondary_id=60 if row['effect'] == 'EFFECT_DEF_SPDEF_DOWN_HIT' else 61,
                display_name=SHORT_DISPLAYS.get(row['name'][5:], row['name'][5:].replace('_', ' ')),
                animation_policy='Reused native animation, not donor animation parity',
                contest_category_policy=('Omitted donor contestCategory zero-initializes to COOL'
                                         if row['name'] == 'MOVE_HEADLONG_RUSH' else 'Gen6+ donor category'),
                policy=('Guaranteed attacker-only one-stage drops via script CERTAIN | AFFECTS_USER, not random opponent secondaries. '
                        'Native Gen3 damage, critical probabilities, contact, Protect, Mirror Move, King\'s Rock eligibility and native ability set retained. '
                        'Mist / Clear Body / White Smoke do not prevent these certain self drops. '
                        'Miss, immunity, failure and Protect skip drops; successful Substitute hits and fainted targets do not block them; floors clamp. '
                        'Punching classification has no native Iron Fist implementation or flag, so no modern punching-ability parity claimed. '
                        'Native moveend and White Herb paths retained, not exercised by catalog tests. '
                        'No Contrary, Simple, Defiant, Competitive or other absent modern ability behavior is promised. '
                        'Headlong Rush uses explicit Gen9 120 power. Static C/data/script seam evidence only, no runtime or gameplay proof.'))
    coverage_path = destination/'tools/expanded_moves/coverage.json'
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.write_text(json.dumps(coverage,indent=2)+'\n')
    print(json.dumps({'ported_moves':len(ports),'moves_count':355+len(ports),'max_serialized_move_id':354+len(ports)}))

if __name__=='__main__': main()
