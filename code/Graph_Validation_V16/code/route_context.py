"""Coarse documentary package-route compatibility, with unknown vocabulary preserved."""
ORAL_SUFFIXES={'oral','oralretard','oralfluessig','oralflüssig'}
PARENTERAL_SUFFIXES={'parenteral','parenteraldepot'}
ROUTE_FAMILIES={'O':'oral','IV':'parenteral','SC':'parenteral','IM':'parenteral','IT':'parenteral'}
def package_family(group):
 suffix=str(group).strip().split()[-1].casefold() if str(group).strip() else ''
 return 'oral' if suffix in ORAL_SUFFIXES else ('parenteral' if suffix in PARENTERAL_SUFFIXES else None)
def decide(group,routes):
 family=package_family(group);tokens={x.strip() for x in str(routes).split(',') if x.strip()}
 if family is None or not tokens:return 'UNDETERMINED'
 mapped={ROUTE_FAMILIES[x] for x in tokens if x in ROUTE_FAMILIES}
 if family in mapped:return 'VERIFIED'
 if any(x not in ROUTE_FAMILIES for x in tokens):return 'UNDETERMINED'
 return 'CONTRADICTED'
