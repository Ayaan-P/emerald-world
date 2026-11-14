"""Literal conditions over this plan's successful receipts, never executable code."""


def validate(condition,dependencies):
    if (type(condition) is not dict or set(condition)!={'step','path','equals'}
        or type(condition['step']) is not str or condition['step'] not in dependencies
        or type(condition['path']) is not str or not condition['path'].startswith('/')
        or len(condition['path'])>120 or len(condition['path'].split('/'))>6
        or type(condition['equals']) not in (str,int,bool,type(None))
        or (type(condition['equals']) is str and len(condition['equals'])>120)):
        raise ValueError('Condition needs a declared prior step, JSON pointer and bounded literal scalar equals')
    # JSON pointer escapes are strict, not arbitrary expressions or traversal.
    for part in condition['path'].split('/')[1:]:
        i=0
        while i<len(part):
            if part[i]=='~':
                if i+1==len(part) or part[i+1] not in '01':raise ValueError('Invalid condition JSON pointer')
                i+=1
            i+=1


def matches(condition,receipts):
    status,value=receipts[condition['step']]
    if status!='succeeded':return False
    for part in condition['path'].split('/')[1:]:
        part=part.replace('~1','/').replace('~0','~')
        if type(value) is dict and part in value:value=value[part]
        elif type(value) is list and part.isdecimal() and str(int(part))==part and int(part)<len(value):value=value[int(part)]
        else:return False # Missing differs from an explicit null.
    return type(value) is type(condition['equals']) and value==condition['equals']
