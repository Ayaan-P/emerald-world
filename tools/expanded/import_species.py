#!/usr/bin/env python3
"""Pinned Expansion-to-legacy species import. Never assigns donor numeric IDs directly.

Emits native C table fragments and original donor assets for the playable selection.
The complete name mapping reserves IDs for subsequent dependency-complete imports.
Unimplemented fields and original donor declarations remain visible in coverage.json.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PIN = 'bb3fd057061cdd7e6a9e79b76abb41924ee44ecc'
# Exact opt-in bindings in ExpandedSpecies_ResolveEncounter. These describe
# implemented support, not observed gameplay or an allowlist for data selection.
IMPLEMENTED_ACQUISITION_ROOTS = tuple(
    dict(map=route, original_species=original, species=species,
         rule='WORLD_RULE_EXPANDED_ROSTER',
         resolver='src/platform/expanded_species.c:ExpandedSpecies_ResolveEncounter')
    for route, original, species in (
        ('MAP_ROUTE101', 'SPECIES_ZIGZAGOON', 'SPECIES_GIMMIGHOUL_ROAMING'),
        ('MAP_ROUTE101', 'SPECIES_WURMPLE', 'SPECIES_MELTAN'),
        ('MAP_ROUTE101', 'SPECIES_POOCHYENA', 'SPECIES_COSMOEM'),
        ('MAP_ROUTE102', 'SPECIES_RALTS', 'SPECIES_TYPE_NULL'),
        ('MAP_ROUTE103', 'SPECIES_ZIGZAGOON', 'SPECIES_TURTWIG'),
        ('MAP_ROUTE103', 'SPECIES_POOCHYENA', 'SPECIES_CHESPIN'),
        ('MAP_ROUTE103', 'SPECIES_MAGIKARP', 'SPECIES_ARROKUDA'),
    ))


# Explicit importer profile, not guessed values for arbitrary donor configuration.
GEN9_PROFILE = {name: 9 for name in (
    'P_UPDATED_STATS', 'P_UPDATED_EXP_YIELDS', 'P_UPDATED_ABILITIES',
    'P_UPDATED_EGG_GROUPS', 'P_UPDATED_EVS', 'P_UPDATED_TYPES')}


def gen9_condition(expr):
    match = re.fullmatch(r'\s*(P_UPDATED_\w+)\s*>=\s*GEN_(\d+)\s*', expr)
    if match and match[1] in GEN9_PROFILE:
        return GEN9_PROFILE[match[1]] >= int(match[2])
    return None


def resolve_gen9(source):
    """Resolve only direct proven comparisons; unknown/malformed trees stay intact."""
    stack = []
    output = []
    active = True
    for line in source.splitlines(keepends=True):
        directive = re.match(r'^\s*#\s*(\w+)(.*)', line)
        if not directive:
            if active:
                output.append(line)
            continue
        value = None
        kind, expr = directive.groups()
        expr = expr.split('//', 1)[0].strip()
        if kind in ('if', 'elif'):
            value = gen9_condition(expr)
            if value is None:
                return source
        if kind == 'if':
            stack.append([active, value, False])
            active = active and value
        elif kind == 'elif' and stack and not stack[-1][2]:
            parent, taken, _ = stack[-1]
            active = parent and not taken and value
            stack[-1][1] = taken or value
        elif kind == 'else' and not expr and stack and not stack[-1][2]:
            parent, taken, _ = stack[-1]
            active = parent and not taken
            stack[-1][2] = True
        elif kind == 'endif' and not expr and stack:
            active = stack.pop()[0]
        else:
            return source
    if stack:
        return source
    resolved = ''.join(output)
    # A whole simple numeric ternary only. No nested/composed expressions.
    def numeric_field(match):
        prefix, condition, yes, no, suffix = match.groups()
        value = gen9_condition(condition)
        return match[0] if value is None else prefix + (yes if value else no) + suffix
    return re.sub(r'^(\s*(?:\.\w+\s*=\s*)?)\((P_UPDATED_\w+\s*>=\s*GEN_\d+)\)\s*\?\s*(\d+)\s*:\s*(\d+)([ \t]*,?[ \t]*)$',
                  numeric_field, resolved, flags=re.M)


def import_blockers(row, donor, supported_tokens):
    """Fail closed on unresolved donor macros, branches and battle dependencies."""
    reasons = []
    source = row['resolved_species_source']
    if row.get('alias_of'):
        reasons.append('alias')
    if not row['level_up_moves'] or 'LEVEL_UP_END' not in row['donor_level_up_source']:
        reasons.append('unresolved_level_up_learnset')
    if '#' in row['resolved_level_up_source']:
        reasons.append('conditional_level_up_learnset')
    if re.search(r'^\s*#', source, re.M):
        reasons.append('conditional_species_declaration')
    if row['missing_level_up_moves']:
        reasons.append('unsupported_level_up_moves')
    if row['missing_normal_abilities']:
        reasons.append('unsupported_abilities')
    if len(row['normal_abilities']) != 2 or row['normal_abilities'][0] == 'ABILITY_NONE':
        reasons.append('unresolved_ability_slots')
    ability_field = re.search(r'\.abilities\s*=\s*\{([^}]+)\}', source)
    if (not ability_field or not re.fullmatch(
            r'\s*ABILITY_\w+\s*,\s*ABILITY_\w+(?:\s*,\s*ABILITY_\w+)?\s*,?\s*', ability_field[1])
            or re.findall(r'ABILITY_\w+', ability_field[1])[:2] != row['normal_abilities']):
        reasons.append('unresolved_ability_slots')
    # Validate the entire serialized expression, not token mentions within an
    # unknown macro or ternary. Optional fields may be absent, never unresolved.
    numeric_fields = ('baseHP', 'baseAttack', 'baseDefense', 'baseSpeed', 'baseSpAttack',
                      'baseSpDefense', 'catchRate', 'expYield', 'eggCycles',
                      'evYield_HP', 'evYield_Attack', 'evYield_Defense', 'evYield_Speed',
                      'evYield_SpAttack', 'evYield_SpDefense', 'height', 'weight',
                      'pokemonScale', 'pokemonOffset', 'trainerScale', 'trainerOffset',
                      'frontPicYOffset', 'backPicYOffset', 'enemyMonElevation', 'iconPalIndex')
    patterns = {key: r'-?\d+' for key in numeric_fields}
    patterns.update(genderRatio=r'(?:MON_GENDERLESS|MON_MALE|MON_FEMALE|PERCENT_FEMALE\(\d+(?:\.\d+)?\))',
                    friendship=r'(?:\d+|STANDARD_FRIENDSHIP)',
                    itemCommon=r'(?:0|ITEM_\w+)', itemRare=r'(?:0|ITEM_\w+)',
                    growthRate=r'GROWTH_\w+', bodyColor=r'BODY_COLOR_\w+',
                    types=r'MON_TYPES\(TYPE_\w+(?:\s*,\s*TYPE_\w+)?\)',
                    eggGroups=r'MON_EGG_GROUPS\(EGG_GROUP_\w+(?:\s*,\s*EGG_GROUP_\w+)?\)',
                    frontPicSize=r'MON_COORDS_SIZE\(\d+,\s*\d+\)',
                    backPicSize=r'MON_COORDS_SIZE\(\d+,\s*\d+\)',
                    speciesName=r'_\("[^"\n]+"\)', categoryName=r'_\("[^"\n]+"\)',
                    natDexNum=r'NATIONAL_DEX_\w+')
    for key, pattern in patterns.items():
        values = re.findall(r'^\s*\.' + key + r'\s*=\s*([^\n]+)', source, re.M)
        if len(values) > 1 or any(not re.fullmatch(pattern, value.strip().removesuffix(',').strip()) for value in values):
            reasons.append('unresolved_serialized_field:' + key)
    # The existing serializer supports these direct fields. Macro-composed
    # species and form templates must not appear dependency-free by omission.
    required = ('baseHP', 'baseAttack', 'baseDefense', 'baseSpeed', 'baseSpAttack',
                'baseSpDefense', 'types', 'catchRate', 'expYield', 'genderRatio',
                'eggCycles', 'friendship', 'growthRate', 'eggGroups', 'abilities',
                'bodyColor', 'speciesName', 'natDexNum', 'description',
                'categoryName', 'height', 'weight', 'pokemonScale', 'pokemonOffset',
                'trainerScale', 'trainerOffset', 'frontPicSize', 'frontPicYOffset',
                'backPicSize', 'backPicYOffset', 'iconPalIndex')
    if any(not re.search(r'\.' + key + r'\s*=', source) for key in required):
        reasons.append('unresolved_species_fields')
    # Held items and stat macros must exist in the target namespace too.
    for token in set(re.findall(r'\b(?:ITEM|TYPE|GROWTH|EGG_GROUP|BODY_COLOR)_\w+', source)):
        # Evolution conditions are not serialized, so their item dependency
        # remains an explicit evolution limitation, not a held-item substitution.
        if token.startswith('ITEM_') and not re.search(r'\.item(?:Common|Rare)\s*=\s*' + token + r'\b', source):
            continue
        if token not in supported_tokens:
            reasons.append('unsupported_token:' + token)
    display = re.search(r'\.speciesName\s*=\s*_\("([^"]+)"\)', source)
    if not display or len(display[1]) > 10:
        reasons.append('legacy_name_slot')
    short = row['name'].removeprefix('SPECIES_').lower()
    directory = donor / 'graphics/pokemon' / ('gimmighoul/roaming' if short == 'gimmighoul_roaming' else short)
    if any(not (directory / filename).is_file() for filename in
           ('back.png', 'normal.pal', 'shiny.pal', 'icon.png', 'footprint.png')) or not any(
               (directory / filename).is_file() for filename in ('front.png', 'anim_front.png')):
        reasons.append('unresolved_graphics')
    return sorted(set(reasons))


def defined_symbols(text, prefix):
    return set(re.findall(r'^#define[ \t]+(' + re.escape(prefix) + r'\w+)\b', text, re.M))


def read_defines(text):
    values = {}
    for name, expr in re.findall(r'^#define\s+(\w+)\s+([^\n]+)', text, re.M):
        expr = expr.split('//')[0].strip()
        for key in re.findall(r'\b[A-Z_]\w*\b', expr):
            if key in values:
                expr = re.sub(r'\b' + key + r'\b', str(values[key]), expr)
        if re.fullmatch(r'[0-9()+\s-]+', expr):
            values[name] = eval(expr, {'__builtins__': {}}, {})
    return values


def donor_enum(text):
    values = {}
    number = -1
    body = text[text.index('enum '):text.index('};')]
    for line in body.splitlines():
        match = re.match(r'\s*(SPECIES_\w+)(?:\s*=\s*(\w+))?\s*,', line)
        if match:
            name, expr = match.groups()
            number = int(expr) if expr and expr.isdigit() else values[expr] if expr else number + 1
            values[name] = number
    return {n: v for n, v in values.items() if n not in ('SPECIES_CUSTOM_START', 'SPECIES_CUSTOM_END')}


def blocks(text):
    result = {}
    for match in re.finditer(r'\[(SPECIES_\w+)\]\s*=\s*\{', text):
        start = match.end() - 1
        depth = 1
        pos = start + 1
        # Braces in donor prose are not used in these declarations.
        while depth and pos < len(text):
            depth += (text[pos] == '{') - (text[pos] == '}')
            pos += 1
        result[match[1]] = text[start:pos]
    return result


def classify_evolutions(source, mapping, native_targets, selected, emit_source=True, max_edges=5):
    """Keep every donor descriptor visible; serialize only exact native level triples.

    EVOLUTION/CONDITIONS use nested braces and parentheses. Token mentions are
    never evidence that an expression, condition or target is supported.
    """
    fields = list(re.finditer(r'\.evolutions\s*=', source))
    if not fields:
        return [], []
    failure = lambda raw: ([], [dict(raw=raw, reasons=['unresolved_evolution_declaration'])])
    if len(fields) != 1 or re.search(r'^\s*#', source, re.M):
        return failure(source[fields[0].start():])
    tail = source[fields[0].end():].lstrip()
    macro = re.match(r'EVOLUTION\s*\(', tail)
    if not macro:
        return failure(tail)
    depth, end = 1, macro.end()
    while depth and end < len(tail):
        depth += (tail[end] == '(') - (tail[end] == ')')
        end += 1
    if depth or not re.match(r'\s*,', tail[end:]):
        return failure(tail)
    body = tail[macro.end():end - 1]
    descriptors = []
    pos = 0
    while pos < len(body):
        if not body[pos:].strip():
            break
        start = pos
        while pos < len(body) and body[pos].isspace():
            pos += 1
        if pos == len(body) or body[pos] != '{':
            return failure(tail[:end])
        depth, start = 1, pos
        pos += 1
        while depth and pos < len(body):
            depth += (body[pos] == '{') - (body[pos] == '}')
            pos += 1
        if depth:
            return failure(tail[:end])
        descriptors.append(body[start:pos])
        while pos < len(body) and body[pos].isspace():
            pos += 1
        if pos < len(body):
            if body[pos] != ',':
                return failure(tail[:end])
            pos += 1
    if not descriptors:
        return failure(tail[:end])
    supported, unsupported = [], []
    for raw in descriptors:
        edge = dict(raw=raw)
        reasons = []
        triple = re.fullmatch(r'\{\s*(EVO_\w+)\s*,\s*(\d+)\s*,\s*(SPECIES_\w+)\s*\}', raw)
        # Preserve readable method/param/target even on conditional descriptors.
        prefix = re.match(r'\{\s*(EVO_\w+)\s*,\s*([^,{}]+)\s*,\s*(SPECIES_\w+)\b', raw)
        if prefix:
            method, param, target = prefix.groups()
            param = param.strip()
            edge.update(method=method, param=int(param) if param.isdecimal() else param, target=target,
                        target_engine_id=mapping.get(target))
            if method != 'EVO_LEVEL':
                reasons.append('unsupported_method')
            if not re.fullmatch(r'[1-9][0-9]*', param) or not 1 <= int(param) <= 100:
                reasons.append('invalid_level_param')
            if target not in native_targets and target not in selected:
                reasons.append('target_not_native_or_selected')
        if not triple:
            reasons.append('unsupported_descriptor')
        if not emit_source:
            reasons.append('source_not_selected_legacy_rows_not_reimported')
        if len(descriptors) > max_edges:
            reasons.append('native_evolution_capacity')
        if reasons:
            edge['reasons'] = reasons
            unsupported.append(edge)
        else:
            supported.append(edge)
    return supported, unsupported


def acquisition_paths(rows, roots=IMPLEMENTED_ACQUISITION_ROOTS):
    """Reachability over already classified, emitted native edges, never donor hints.

    The first discovered path is retained, giving stable root ordering and finite
    traversal even with cycles. A native/base target may be reached but its legacy
    donor edges are not followed because those rows are never reimported.
    """
    by_name = {row['name']: row for row in rows}
    paths = {root['species']: dict(root=dict(root), evolutions=[]) for root in roots}
    pending = list(paths)
    for name in pending:
        for edge in by_name.get(name, {}).get('supported_evolutions', []):
            target = edge['target']
            if target not in paths:
                paths[target] = dict(root=paths[name]['root'],
                                     evolutions=paths[name]['evolutions'] + [dict(source=name, **edge)])
                pending.append(target)
    return paths


def emit(out, name, text):
    path = out / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def generate(donor, out):
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=donor, text=True).strip()
    if commit != PIN:
        raise ValueError('donor source pin mismatch: ' + commit)
    # The committed legacy header is the immutable save-ID baseline, not a generated header.
    legacy_text = subprocess.check_output(['git', 'show', 'HEAD:include/constants/species.h'], cwd=ROOT, text=True)
    legacy = read_defines(legacy_text)
    donor_ids = donor_enum((donor / 'include/constants/species.h').read_text())
    info = {}
    for path in sorted((donor / 'src/data/pokemon/species_info').glob('*.h')):
        info.update(blocks(path.read_text()))
    learnsets = {}
    for path in sorted((donor / 'src/data/pokemon/level_up_learnsets').glob('*.h')):
        learnsets.update(dict(re.findall(r'(s\w+LevelUpLearnset)\[\] = \{(.*?)\};', path.read_text(), re.S)))
    teachable = dict(re.findall(r'(s\w+TeachableLearnset)\[\] = \{(.*?)\};', (donor / 'src/data/pokemon/teachable_learnsets.h').read_text(), re.S))
    moves = defined_symbols((ROOT / 'include/constants/moves.h').read_text(), 'MOVE_') - {'MOVE_NONE'}
    abilities = defined_symbols((ROOT / 'include/constants/abilities.h').read_text(), 'ABILITY_')
    mapping = {}
    canonical = {}
    # Assign the tracer first, then stable donor order. Aliases share one engine ID.
    next_id = 440
    for name in ['SPECIES_GIMMIGHOUL_ROAMING'] + list(donor_ids):
        if name in mapping:
            continue
        donor_id = donor_ids[name]
        base_name = {'SPECIES_CASTFORM_NORMAL': 'SPECIES_CASTFORM', 'SPECIES_DEOXYS_NORMAL': 'SPECIES_DEOXYS'}.get(name, name)
        if donor_id in canonical:
            mapping[name] = mapping[canonical[donor_id]]
        elif base_name in legacy:
            mapping[name] = legacy[base_name]
            canonical[donor_id] = name
        else:
            mapping[name] = next_id
            canonical[donor_id] = name
            next_id += 1
    rows = []
    for name, donor_id in donor_ids.items():
        original_source = info.get(name, info.get(canonical[donor_id], ''))
        source = resolve_gen9(original_source)
        lm = re.search(r'\.levelUpLearnset\s*=\s*(\w+)', source)
        tm = re.search(r'\.teachableLearnset\s*=\s*(\w+)', source)
        original_level_source = learnsets.get(lm[1], '') if lm else ''
        level_source = resolve_gen9(original_level_source)
        level = [[int(l), m] for l, m in re.findall(r'LEVEL_UP_MOVE\(\s*(\d+),\s*(MOVE_\w+)\)', level_source)]
        teach_source = teachable.get(tm[1], '') if tm else ''
        abs_match = re.search(r'\.abilities\s*=\s*\{([^}]+)', source)
        abs_names = re.findall(r'ABILITY_\w+', abs_match[1]) if abs_match else []
        unsupported = []
        if '.evolutions' in source:
            unsupported.append('evolution')
        if len(abs_names) > 2 and abs_names[2] != 'ABILITY_NONE':
            unsupported.append('hidden_ability_slot')
        if '.formSpeciesIdTable' in source:
            unsupported.append('form_change')
        status = 'legacy' if mapping[name] < 440 else 'reserved_not_playable'
        row = dict(name=name, donor_id=donor_id, engine_id=mapping[name], status=status,
                   level_up_moves=level, missing_level_up_moves=sorted({m for _, m in level} - moves),
                   missing_abilities=sorted(set(abs_names) - abilities),
                   missing_normal_abilities=sorted(set(abs_names[:2]) - abilities),
                   supported_slots=[], hidden_ability_supported=False, unsupported_features=unsupported,
                   normal_abilities=abs_names[:2], hidden_ability=abs_names[2] if len(abs_names) > 2 else None,
                   donor_species_source=original_source, donor_level_up_source=original_level_source,
                   resolved_species_source=source, resolved_level_up_source=level_source,
                   donor_teachable_source=teach_source,
                   missing_teachable_moves=sorted(set(re.findall(r'MOVE_\w+', teach_source)) - moves - {'MOVE_UNAVAILABLE'}))
        if canonical[donor_id] != name:
            row['alias_of'] = canonical[donor_id]
        rows.append(row)
    supported_tokens = set()
    for filename in ('items.h', 'pokemon.h', 'battle.h'):
        supported_tokens.update(re.findall(r'^#define\s+(\w+)', (ROOT / 'include/constants' / filename).read_text(), re.M))
    selected = []
    for row in rows:
        row['import_blockers'] = import_blockers(row, donor, supported_tokens)
        if row['engine_id'] >= 440 and not row['import_blockers']:
            selected.append(row['name'])
        row['battle_supported'] = row['name'] in selected
        row['supported_slots'] = [0, 1] if row['battle_supported'] else []
        if row['engine_id'] >= 440:
            row['status'] = 'native_selected' if row['battle_supported'] else 'reserved_not_playable'
    # Keep established acquisition ordering stable as selection grows.
    root_names = [root['species'] for root in IMPLEMENTED_ACQUISITION_ROOTS]
    selected = [name for name in root_names if name in selected] + [name for name in selected if name not in root_names]
    for name in root_names:
        row = next(r for r in rows if r['name'] == name)
        if row['import_blockers']:
            raise ValueError('existing acquisition has unresolved dependencies: ' + name + ': ' + str(row['import_blockers']))
    native_ids = {value for name, value in legacy.items()
                  if name.startswith('SPECIES_') and not name.startswith('SPECIES_OLD_UNOWN_')
                  and 0 < value < legacy['SPECIES_EGG']}
    native_targets = {name for name, value in mapping.items() if value in native_ids}
    for row in rows:
        supported, unsupported = classify_evolutions(
            row['resolved_species_source'], mapping, native_targets, set(selected),
            emit_source=row['name'] in selected)
        row['supported_evolutions'] = supported
        row['unsupported_evolutions'] = unsupported
        if not unsupported and 'evolution' in row['unsupported_features']:
            row['unsupported_features'].remove('evolution')
    paths = acquisition_paths(rows)
    for row in rows:
        row['obtainable'] = row['name'] in paths
        row['acquisition_path'] = paths.get(row['name'])
    manifest = dict(schema_version=5, gen9_profile=GEN9_PROFILE, source_commit=commit, legacy_last_graphics_id=439,
                    playable_selection=selected, obtainable_selection=list(paths),
                    implemented_acquisition_roots=list(IMPLEMENTED_ACQUISITION_ROOTS),
                    acquisition_scope='Implemented opt-in encounter roots plus transitive supported emitted evolution edges, not native gameplay proof. All matching staged dependencies must be integrated together.',
                    native_runtime_count=max(mapping[n] for n in selected) + 1,
                    battle_support_requires=['modern_split', 'native expanded move/ability tables',
                                             'matching generated species, dex and graphics headers'],
                    support_scope='battle_supported and supported_slots describe emitted native-normal slots [0,1] only, not hidden abilities, acquisition or full donor feature parity; legacy rows are not reimported',
                    ability_policy='CreateBoxMon uses personality & 1 only when normal slot 1 is nonzero, otherwise slot 0. Hidden slot 2 is metadata only and never substituted. No saved ABI changes.',
                    support_limits=dict(
                        level_up='complete resolved donor level-up learnset with no move substitution',
                        teachable='native TM/HM and tutor subset only; unavailable_teachable_moves lists omissions',
                        hidden_abilities='unsupported for every emitted species, including hidden abilities with existing battle effect symbols',
                        acquisition='seven explicit opt-in Route 101/102/103 roots including Route 103 fishing Magikarp/Arrokuda plus closure over supported emitted native evolution edges only; other emitted species including Kubfu have no implemented acquisition path; support is not gameplay proof',
                        runtime='staged output only; all matching generated files and headers must be promoted together before runtime selection changes',
                        rendering='static first front frame only; donor cries and followers are not integrated',
                        evolution='only exact unconditional EVO_LEVEL triples with levels 1..100 and native/base or selected targets are emitted; supported_evolutions and unsupported_evolutions record every descriptor; legacy rows are untouched',
                        donor_features='egg moves, form changes and expanded Dex persistence are not implied by battle_supported'),
                    promotion_headers=['include/constants/expanded_species.h',
                                       'include/constants/expanded_pokedex.h',
                                       'include/expanded_species_graphics.h'],
                    numeric_profile='Gen 9', level_up_profile='highest available donor generation per learnset (Gen 9 preferred)',
                    policy='No unsupported move, ability or evolution edge is substituted. Reserved species are not playable. Only supported_evolutions are integrated; other evolution descriptors, form changing, cry audio and expanded Dex persistence remain explicit limitations.',
                    species=rows)
    emit(out, 'tools/expanded/coverage.json', json.dumps(manifest, indent=2) + '\n')
    prefix = 'src/data/pokemon/expanded/'
    outputs = {name: [] for name in ['evolution', 'species_info', 'learnsets', 'learnset_pointers', 'names', 'tmhm', 'tutors', 'graphics', 'graphics_externs', 'dex_entries', 'dex_text', 'front_table', 'back_table', 'palette_table', 'shiny_table', 'front_coords', 'back_coords', 'footprints', 'elevations', 'icon_table', 'icon_palettes', 'animations', 'animation_pointers', 'dex_map', 'species_constants', 'dex_constants', 'playable_cases']}
    tm_source = (ROOT / 'src/data/pokemon/tmhm_learnsets.h').read_text()
    tutor_source = (ROOT / 'src/data/pokemon/tutor_learnsets.h').read_text()
    tm_names = set(re.findall(r'\.(\w+)\s*=\s*TRUE', tm_source))
    tutor_names = set(re.findall(r'TUTOR\((MOVE_\w+)\)', tutor_source))
    dex_source = (donor / 'include/constants/pokedex.h').read_text().split('};', 1)[0]
    dex_ids = {name: n for n, name in enumerate(re.findall(r'^\s*(NATIONAL_DEX_\w+)\s*,', dex_source, re.M))}
    assets = []
    for name in selected:
        row = next(r for r in rows if r['name'] == name)
        source = row['resolved_species_source']
        short = name.removeprefix('SPECIES_').lower()
        symbol = ''.join(word.title() for word in short.split('_'))
        def field(key, default=None):
            value = re.search(r'\.' + key + r'\s*=\s*([^\n]+)', source)
            if not value:
                if default is not None:
                    return default
                raise ValueError('missing selected field: ' + name + '.' + key)
            expr = value[1].strip().removesuffix(',').strip()
            return expr
        normal_abilities = re.findall(r'ABILITY_\w+', re.search(r'\.abilities\s*=\s*\{([^}]+)', source)[1])
        stats = []
        for key in ['baseHP', 'baseAttack', 'baseDefense', 'baseSpeed', 'baseSpAttack', 'baseSpDefense', 'catchRate', 'expYield', 'genderRatio', 'eggCycles', 'friendship', 'growthRate', 'bodyColor']:
            stats.append('    .' + key + ' = ' + field(key) + ',')
        for key in ['evYield_HP', 'evYield_Attack', 'evYield_Defense', 'evYield_Speed', 'evYield_SpAttack', 'evYield_SpDefense', 'itemCommon', 'itemRare']:
            stats.append('    .' + key + ' = ' + field(key, '0') + ',')
        for key, macro in [('types', 'MON_TYPES'), ('eggGroups', 'MON_EGG_GROUPS')]:
            values = [x.strip() for x in re.search(r'\.' + key + r'\s*=\s*' + macro + r'\(([^)]+)', source)[1].split(',')]
            if len(values) == 1:
                values *= 2
            stats.append('    .' + key + ' = {' + ', '.join(values) + '},')
        stats.append('    .abilities = {' + ', '.join(normal_abilities[:2]) + '},')
        level_edges = row['supported_evolutions']
        if level_edges:
            outputs['evolution'].append('[' + name + '] = {' + ', '.join(
                '{%s, %d, %s}' % (edge['method'], edge['param'], edge['target'])
                for edge in level_edges) + '},')
        outputs['species_info'].append('[' + name + '] = {\n' + '\n'.join(stats) + '\n},')
        outputs['learnsets'].append('static const u16 sExpanded' + symbol + 'LevelUpLearnset[] = {\n' + ''.join('    LEVEL_UP_MOVE(%d, %s),\n' % (level, move) for level, move in row['level_up_moves']) + '    LEVEL_UP_END\n};')
        outputs['learnset_pointers'].append('[' + name + '] = sExpanded' + symbol + 'LevelUpLearnset,')
        display = re.search(r'\.speciesName\s*=\s*_\("([^"]+)"\)', source)[1].upper()
        if len(display) > 10:
            raise ValueError('name exceeds the legacy 10-character slot: ' + name)
        outputs['names'].append('[' + name + '] = _("' + display + '"),')
        teach_moves = set(re.findall(r'MOVE_\w+', row['donor_teachable_source'])) - {'MOVE_UNAVAILABLE'}
        missing = teach_moves - {'MOVE_' + n for n in tm_names} - tutor_names
        # Preserve every unavailable teachable entry explicitly; never silently grant or replace it.
        row['unavailable_teachable_moves'] = sorted(missing)
        outputs['tmhm'].append('[' + name + '] = { .learnset = {\n' + ''.join('    .%s = TRUE,\n' % m[5:] for m in sorted(teach_moves) if m[5:] in tm_names) + '} },')
        outputs['tutors'].append('[' + name + '] = (' + (' | '.join('TUTOR(%s)' % m for m in sorted(teach_moves & tutor_names)) or '0') + '),')
        dex_name = field('natDexNum')
        outputs['species_constants'].append('#define ' + name + ' ' + str(row['engine_id']))
        outputs['dex_constants'].append('#define ' + dex_name + ' ' + str(dex_ids[dex_name]))
        outputs['dex_map'].append('{' + name + ', ' + dex_name + '},')
        outputs['playable_cases'].append('case ' + name + ':')
        text = re.search(r'\.description\s*=\s*COMPOUND_STRING\((.*?)\),', source, re.S)[1]
        outputs['dex_text'].append('const u8 gExpanded' + symbol + 'PokedexText[] = _(' + text + ');')
        dex_fields = ['categoryName', 'height', 'weight', 'pokemonScale', 'pokemonOffset', 'trainerScale', 'trainerOffset']
        outputs['dex_entries'].append('[' + dex_name + '] = {\n' + '\n'.join('    .' + key + ' = ' + field(key) + ',' for key in dex_fields) + '\n    .description = gExpanded' + symbol + 'PokedexText,\n},')
        for outkey, ctype, kind, filename, suffix in [('front_table','u32','Front','front.png','.4bpp.lz'),('back_table','u32','Back','back.png','.4bpp.lz'),('palette_table','u32','Palette','normal.pal','.gbapal.lz'),('shiny_table','u32','ShinyPalette','shiny.pal','.gbapal.lz'),('icon_table','u8','Icon','icon.png','.4bpp'),('footprints','u8','Footprint','footprint.png','.1bpp')]:
            ident = 'gExpanded' + kind + '_' + symbol
            outputs['graphics'].append('const ' + ctype + ' ' + ident + '[] = INCGFX_' + ctype.upper() + '("graphics/expanded/' + short + '/' + filename + '", "' + suffix + '");')
            outputs['graphics_externs'].append('extern const ' + ctype + ' ' + ident + '[];')
            if outkey in ['front_table', 'back_table']:
                entry = 'SPECIES_SPRITE(' + name[8:] + ', ' + ident + '),'
            elif outkey in ['palette_table','shiny_table']:
                entry = ('SPECIES_PAL' if outkey == 'palette_table' else 'SPECIES_SHINY_PAL') + '(' + name[8:] + ', ' + ident + '),'
            else:
                entry = '[' + name + '] = ' + ident + ','
            outputs[outkey].append(entry)
        outputs['front_coords'].append('[' + name + '] = { .size = ' + field('frontPicSize') + ', .y_offset = ' + field('frontPicYOffset') + ' },')
        outputs['back_coords'].append('[' + name + '] = { .size = ' + field('backPicSize') + ', .y_offset = ' + field('backPicYOffset') + ' },')
        outputs['elevations'].append('[' + name + '] = ' + field('enemyMonElevation', '0') + ',')
        outputs['icon_palettes'].append('[' + name + '] = ' + field('iconPalIndex') + ',')
        # Legacy SINGLE_ANIMATION has idle slot 0 and entrance slot 1. Both
        # must use frame 0 because the selected front assets are static crops.
        if not outputs['animations']:
            outputs['animations'].append('/* Match the legacy idle/entrance slots while using only the imported frame 0. */')
        outputs['animations'].append('static const union AnimCmd sExpanded' + symbol + 'Frame[] = { ANIMCMD_FRAME(0, 1), ANIMCMD_END };\nstatic const union AnimCmd *const sExpanded' + symbol + 'Anims[] = { sExpanded' + symbol + 'Frame, sExpanded' + symbol + 'Frame };')
        outputs['animation_pointers'].append('[' + name + '] = sExpanded' + symbol + 'Anims,')
        donor_dir = donor / 'graphics/pokemon' / ('gimmighoul/roaming' if short == 'gimmighoul_roaming' else short)
        for filename in ['front.png', 'back.png', 'normal.pal', 'shiny.pal', 'icon.png', 'footprint.png']:
            source_asset = donor_dir / filename
            dest = out / 'graphics/expanded' / short / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            transform = 'identity'
            if filename == 'front.png' and not source_asset.exists():
                from PIL import Image
                source_asset = donor_dir / 'anim_front.png'
                with Image.open(source_asset) as image:
                    image.crop((0, 0, 64, 64)).save(dest)
                transform = 'first_64x64_frame; static animation explicitly selected'
            else:
                shutil.copyfile(source_asset, dest)
            assets.append(dict(path=str(dest.relative_to(out)), donor_path=str(source_asset.relative_to(donor)), source_sha256=hashlib.sha256(source_asset.read_bytes()).hexdigest(), sha256=hashlib.sha256(dest.read_bytes()).hexdigest(), transform=transform))
        row['unsupported_features'] += ['cry_audio', 'overworld_follower']
        if not row['obtainable']:
            row['unsupported_features'].append('acquisition_route')
        # Acquisition/evolution support does not establish expanded journal persistence.
        row['unsupported_features'].append('expanded_dex_persistence')
        if '.eggMoveLearnset' in source:
            row['unsupported_features'].append('egg_moves')
        row['rendering_profile'] = 'donor colors, front/back/icon/footprint, static first front frame'
    for name, lines in outputs.items():
        emit(out, prefix + name + ('.h' if name == 'graphics' else '.inc'), '\n'.join(lines) + '\n')
    emit(out, 'include/constants/expanded_species.h', '#ifndef GUARD_CONSTANTS_EXPANDED_SPECIES_H\n#define GUARD_CONSTANTS_EXPANDED_SPECIES_H\n' + '\n'.join(outputs['species_constants']) + '\n#define SPECIES_TABLE_COUNT ' + str(manifest['native_runtime_count']) + '\n#endif\n')
    emit(out, 'include/constants/expanded_pokedex.h', '#ifndef GUARD_CONSTANTS_EXPANDED_POKEDEX_H\n#define GUARD_CONSTANTS_EXPANDED_POKEDEX_H\n' + '\n'.join(outputs['dex_constants']) + '\n#endif\n')
    emit(out, 'include/expanded_species_graphics.h', '\n'.join(outputs['graphics_externs']) + '\n')
    emit(out, 'tools/expanded/coverage.json', json.dumps(manifest, indent=2) + '\n')
    emit(out, 'tools/expanded/assets.json', json.dumps(dict(source_commit=commit, assets=assets), indent=2) + '\n')
    print(json.dumps(dict(source_commit=commit, donor_names=len(rows), native_selected=len(selected), reserved=sum(r['status'] == 'reserved_not_playable' for r in rows), output=str(out))))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--donor', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    generate(args.donor.resolve(), args.output.resolve())
