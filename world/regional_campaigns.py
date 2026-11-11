"""Bounded discovery for existing campaign visits; no path or story grants."""
def inspect(server,actor,row,args):
    if set(args)-{'region','offset'}:raise ValueError('Use region and offset')
    region=args.get('region','hoenn');offset=args.get('offset',0)
    if region not in ('hoenn','kanto') or type(offset) is not int or offset<0 or offset>1024:raise ValueError('Invalid destination page')
    from .build_catalog import catalog_maps
    base=catalog_maps()
    if region=='kanto':
        from .combined_regions import catalog,DIGEST
        if not getattr(server,'combined_regions',False):raise ValueError('Kanto campaigns require the combined authority profile')
        entries=[m for key,m in catalog().items() if key not in base];registry=DIGEST
    else:entries=list(base.values());registry=None
    entries.sort(key=lambda m:(m['group'],m['num']))
    rows=[dict(map=m['name'],group=m['group'],num=m['num'],width=m['width'],height=m['height']) for m in entries[offset:offset+16]]
    return dict(region=region,registry=registry,destinations=rows,next=offset+16 if offset+16<len(entries) else None,
        semantics='Map bounds only, not reachable-floor or unlocked-story proof. Author visit {label,point,registry} for combined destinations. Players travel normally and voluntarily check in using fresh admitted client presence. No native story progress or automatic travel.')
