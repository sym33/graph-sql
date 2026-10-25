"""Documentary route policies at three declared resolutions."""
import re
TOKENS={'O','IV','SC','IM','IT','SR','Inhal','ET'}
FAMILIES={'O':'oral','IV':'parenteral','SC':'parenteral','IM':'parenteral','IT':'parenteral'}
def family(group):
 token=str(group).strip().split()[-1].casefold() if str(group).strip() else ''
 if token in {'oral','oralretard','oralfluessig','oralflüssig'}:return 'oral'
 if token in {'parenteral','parenteraldepot'}:return 'parenteral'
 return None
def explicit_routes(package):
 routes=set()
 for route,pattern in {'IV':r'(?<!\w)i\.?\s*v\.?(?!\w)','SC':r'(?<!\w)s\.?\s*c\.?(?!\w)|\bsubkutan\b','IM':r'(?<!\w)i\.?\s*m\.?(?!\w)','IT':r'(?<!\w)i\.?\s*t\.?(?!\w)'}.items():
  if re.search(pattern,package,re.I):routes.add(route)
 return routes
def available_routes(group,package,policy):
 f=family(group)
 if policy=='coarse':return {k for k,v in FAMILIES.items() if v==f} if f else set()
 if policy not in {'exact_code','explicit_formulation'}:raise ValueError(policy)
 codes={'O'} if f=='oral' else explicit_routes(package) if f=='parenteral' else set()
 if policy=='explicit_formulation':
  if f=='oral' and not re.search(r'\b(?:filmtabl|tabl|kaps)\b',package,re.I):return set()
  if f=='parenteral' and not re.search(r'\b(?:inf|inj|trockensub)\b',package,re.I):return set()
 return codes
def assess(group,package,tariff,policy):
 known=available_routes(group,package,policy);options={x.strip() for x in tariff.split(',') if x.strip()}
 if not known or not options:return 'UNDETERMINED'
 if known&options:return 'VERIFIED'
 vocabulary=set(FAMILIES) if policy=='coarse' else TOKENS
 if not options<=vocabulary:return 'UNDETERMINED'
 return 'CONTRADICTED'
