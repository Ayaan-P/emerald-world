from pathlib import Path
import re

def function_span(text, name):
    match = re.search(r'^([^\n;]*\b' + re.escape(name) + r'\([^;\n]*\))\s*(?:(?://[^\n]*\n|/\*.*?\*/)\s*)*\n?\{', text, re.M|re.S)
    if not match:
        raise ValueError('function definition missing: '+name)
    start=match.start(); index=text.index('{',match.start()); depth=0
    token=re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]', re.S)
    for found in token.finditer(text,index):
        value=found.group()
        if value=='{':depth+=1
        elif value=='}':
            depth-=1
            if not depth:return start,found.end()
    raise ValueError('unbalanced function '+name)

def function_text(path,name):
    text=Path(path).read_text();a,b=function_span(text,name);return text[a:b]
