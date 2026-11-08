"""Public authored trainer reference, never a player's party or completion state."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

SOURCE_PATH = 'src/data/trainers.party'
ANCHORS = (
    ('ROXANNE', 'Rustboro', 'rock'), ('BRAWLY', 'Dewford', 'fighting'),
    ('WATTSON', 'Mauville', 'electric'), ('FLANNERY', 'Lavaridge', 'fire'),
    ('NORMAN', 'Petalburg', 'normal'), ('WINONA', 'Fortree', 'flying'),
    ('TATE_AND_LIZA', 'Mossdeep', 'psychic'), ('JUAN', 'Sootopolis', 'water'),
)


def parse_parties(source):
    """Parse this source's blank-separated export grammar; reject directives."""
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
    if re.search(r'^\s*#', source, re.M):
        raise ValueError('Conditional trainer sources require preprocessing')
    result = []
    for block in re.split(r'^=== ', source, flags=re.M)[1:]:
        identity, body = block.split(' ===', 1)
        if not re.fullmatch(r'TRAINER_[A-Z0-9_]+', identity):
            raise ValueError('Invalid trainer identity')
        chunks = re.split(r'\n\s*\n', body.strip())
        fields = dict(line.split(': ', 1) if ': ' in line else (line.rstrip(':'), '')
                      for line in chunks[0].splitlines())
        party = []
        for chunk in chunks[1:]:
            lines = chunk.strip().splitlines()
            if not lines:
                continue
            mon = {'species_and_item': lines[0], 'moves': []}
            for line in lines[1:]:
                if line.startswith('- '):
                    mon['moves'].append(line[2:])
                elif ': ' in line:
                    key, value = line.split(': ', 1)
                    mon[key.lower().replace(' ', '_')] = value
                else:
                    raise ValueError('Unsupported party line: ' + line)
            if 'level' not in mon:
                raise ValueError('Explicit source level required')
            mon['level'] = int(mon['level'])
            mon['moves_source'] = 'explicit' if mon['moves'] else 'native_level_up_defaults'
            party.append(mon)
        result.append({'id': identity, 'name': fields.get('Name'),
                       'class': fields.get('Class'), 'ai': fields.get('AI'),
                       'items': fields.get('Items'),
                       'battle_format': fields.get('Battle Type',
                           'doubles' if fields.get('Double Battle') == 'Yes' else 'singles'),
                       'party': party})
    if len({t['id'] for t in result}) != len(result):
        raise ValueError('Duplicate trainer identity')
    return result


def build_reference(source, revision):
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Exact engine commit required')
    trainers = parse_parties(source)
    indexed = {trainer['id']: trainer for trainer in trainers}
    anchors = []
    for order, (name, town, theme) in enumerate(ANCHORS, 1):
        trainer = dict(indexed['TRAINER_' + name + '_1'])
        trainer.update(story_order=order, town=town, theme=theme,
                       theme_source='editorial annotation of original gym identity')
        anchors.append(trainer)
    mons = [mon for trainer in trainers for mon in trainer['party']]
    species = [mon['species_and_item'].split(' @ ')[0] for mon in mons]
    return {'version': 1, 'provenance': {
        'repository': 'Ayaan-P/pokeemerald-expansion-native', 'revision': revision,
        'path': SOURCE_PATH, 'sha256': hashlib.sha256(source.encode()).hexdigest(),
        'git_blob_sha1': hashlib.sha1(('blob ' + str(len(source.encode())) + '\0').encode() + source.encode()).hexdigest()},
        'scope': 'Hoenn trainer definitions only; includes rematches and unused definitions; not map reachability or live state',
        'summary': {'trainer_definitions': len(trainers), 'party_slots': len(mons),
                    'distinct_species_labels': len(set(species)),
                    'party_size_histogram': dict(sorted(Counter(len(t['party']) for t in trainers).items())),
                    'explicit_movesets': sum(bool(m['moves']) for m in mons),
                    'most_frequent_species': Counter(species).most_common(10)},
        'gym_anchors': anchors,
        'design_references': [
            {'url': 'https://github.com/resetes12/pokeemerald',
             'lesson': 'Modern Emerald separates level caps, party limits, items and IV/EV settings. Treat these as separate challenge axes, not one opaque difficulty score.'},
            {'url': 'https://github.com/segabl/exalted-emerald',
             'lesson': 'Exalted Emerald describes rematch party growth and AI/level changes. Preserve character identity while changing team strength deliberately.'}],
        'reuse': 'Design observations only. No donor code or assets copied; public visibility alone does not grant reuse permission.'}


def author_context(request):
    """Bounded public reference selected by literal request, with no private input."""
    data = json.loads(Path(__file__).with_name('trainer_reference.json').read_text())
    text = request.casefold()
    matches = [t for t in data['gym_anchors']
               if t['name'].casefold() in text or t['town'].casefold() in text]
    return {'provenance': data['provenance'], 'scope': data['scope'],
            'summary': data['summary'], 'design_references': data['design_references'],
            'reuse': data['reuse'],
            'story_progression': [{'id': t['id'], 'town': t['town'], 'theme': t['theme'],
                                   'levels': [m['level'] for m in t['party']],
                                   'battle_format': t['battle_format']} for t in data['gym_anchors']],
            'matched_teams': matches[:3], 'matched_teams_omitted': max(0, len(matches)-3),
            'constraints': [
                'Static source snapshot, not verification of the running engine or current world rules.',
                'Never infer badges, defeated trainers, accessible encounters, inventory or player party from these definitions.',
                'Native moves, abilities and world settings can change difficulty; theme is editorial, not a type-effectiveness simulation.',
                'Use teams as design references, not permission or capability to edit native trainers.',
                'Generated dialogue is not battle completion evidence. Do not promise native battles, catches, quest flags or item rewards without a supported verified mechanism.',
                'Make challenges optional and respect selected player purposes. Do not import donor hack teams or assets.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('revision')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(build_reference(args.source.read_text(), args.revision), indent=2) + '\n')


if __name__ == '__main__':
    main()
