"""Reviewed original script paths. These are not author-defined movement tiles."""
PATHS={
 'rydel_step':dict(actor='canon_rydel',map='MauvilleCity_BikeShop',local=1,points=[(2,5),(3,5),(2,5)]),
 'steven_study':dict(actor='canon_steven',map='MossdeepCity_StevensHouse',local=1,points=[(6,5),(5,5),(4,5),(5,5),(6,5)]),
}
def binding(actor,key):
 path=PATHS.get(key)
 if not path or path['actor']!=actor:raise ValueError('Reviewed original actor path required')
 return path
