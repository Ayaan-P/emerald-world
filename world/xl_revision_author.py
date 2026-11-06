"""Opt-in model-authored terrain revision for an existing offline XL story."""
import argparse,json
from pathlib import Path
from . import author_cave
from .xl_versioned_world import decode,revise,SIZE
from .map_store import write_map,validate_replacement

def prompt_for_revision(theme,characters):
    prompt=author_cave.prompt_for(theme,large=True,wilds=True,xl=True)
    prompt=prompt.replace('"corridor_width":1}', '"corridor_width":1,"paint":[{"x":10,"y":10,"width":5,"height":5,"terrain":"tall_grass"}]}')
    positions=[{'x':c['x'],'y':c['y']} for c in characters]
    constraints=('Paint has zero to 64 ordered rectangles with integer x,y,width,height inside 1..125 and terrain water, grass or tall_grass. '
                 'Keep entrance (1,1), exit (125,125), and approach (125,124) as grass. '
                 'All walkable cells and these existing character positions must stay reachable: '+json.dumps(positions,separators=(',',':'))+'. '
                 'Do not return characters or story rules; they remain unchanged. Later rectangles override earlier ones. ')
    return prompt.replace("The following JSON\nstring is a player's design theme",constraints+"The following JSON string is a player's design theme")

def author_revision(theme,previous,*,timeout=120,attempts=1):
    _,_,characters,_,_=decode(previous)  # reject invalid source before any provider call
    prompt=prompt_for_revision(theme,characters)
    def validate(wire):
        doc=json.loads(author_cave.author_message(wire))
        if type(doc) is not dict:raise ValueError('invalid revision')
        blueprint=dict(doc);paint=blueprint.pop('paint',None)
        return revise(previous,blueprint,paint)
    return author_cave.request_validated(prompt,validate,timeout=timeout,attempts=attempts)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('theme');p.add_argument('--previous',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--replace-output',action='store_true');p.add_argument('--timeout',type=float,default=120);p.add_argument('--attempts',type=int,default=1);a=p.parse_args(argv)
    try:
        with a.previous.open('rb') as f:previous=f.read(SIZE+1)
        decode(previous)
        if a.replace_output:validate_replacement(a.output)
        else:
            try:a.output.lstat()
            except FileNotFoundError:pass
            else:raise FileExistsError('output exists')
        blob=author_revision(a.theme,previous,timeout=a.timeout,attempts=a.attempts)
        write_map(a.output,blob,replace=a.replace_output)
    except (OSError,ValueError,TypeError,TimeoutError,UnicodeError):p.exit(1,'Could not author the XL revision.\n')
    print('Wrote validated XL revision:',a.output)
if __name__=='__main__':main()
