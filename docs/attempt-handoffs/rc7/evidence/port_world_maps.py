from pathlib import Path
import json
import shutil
root=Path(__file__).resolve().parents[1]
native=root/'engines/expansion-native'
groups=json.loads((native/'data/maps/map_groups.json').read_text())
name='gMapGroup_GeneratedWorld'
if name not in groups['group_order']:
    groups['group_order'].insert(34,name)
groups[name]=['GeneratedWorld_Cave','GeneratedWorld_Wilds']
(native/'data/maps/map_groups.json').write_text(json.dumps(groups,indent=2)+'\n')
layouts=json.loads((native/'data/layouts/layouts.json').read_text())
old=json.loads((root/'data/layouts/layouts.json').read_text())
for layout in old['layouts']:
    if layout['id'].startswith('LAYOUT_GENERATED_WORLD_'):
        value=dict(layout,layout_version='emerald')
        layouts['layouts']=[x for x in layouts['layouts'] if x['id']!=value['id']]
        layouts['layouts'].append(value)
(native/'data/layouts/layouts.json').write_text(json.dumps(layouts,indent=2)+'\n')
for name in groups[name]:
    shutil.copytree(root/'data/maps'/name,native/'data/maps'/name,dirs_exist_ok=True)
print('Carried both existing generated-world maps and layouts into the complete native map set.')
