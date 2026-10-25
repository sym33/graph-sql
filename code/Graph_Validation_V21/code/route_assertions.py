"""Conservative, section-local route assertions; contradictions never become support."""
import re
PATTERNS={'IV':[r'\bintravenous use\b',r'should be administered via an intravenous infusion only',r'by slow intravenous \(iv\) infusion'], 'SC':[r'for subcutaneous (?:injection|use) only',r'should (?:always be administered as|be given by) (?:a )?subcutaneous injection'], 'O':[r'\bfor oral use\b',r'should be taken orally']}
ROUTES={'IV':'intravenous','SC':'subcutaneous','O':'oral'}
def extract(text):
 text=' '.join(text.lower().split());negatives=[];positives=[];conditional=[];qualified=[]
 for route,word in ROUTES.items():
  form=word+r'(?:ly)?';noun=r'(?:\s+(?:use|administration|injection|infusion))?'
  governors=r'(?:not|never|no)\s+(?:(?:intended|recommended|approved|suitable|indicated|authori[sz]ed)\s+)?(?:(?:for|be\s+(?:administered|given|used)|administer)\s+)?(?:(?:via|by|as|an?|the)\s+)*'
  patterns=[r'\b'+governors+form+noun, r'\b'+form+noun+r'\s+(?:is|are)\s+not\s+(?:recommended|intended|approved|suitable|allowed|indicated)']
  for pattern in patterns:
   for match in re.finditer(pattern,text):
    item={'route':route,'span':list(match.span()),'text':match.group()}
    if re.match(r'\s+(?:push|bolus)\b',text[match.end():]):qualified.append(item)
    else:negatives.append(item)
 for route,patterns in PATTERNS.items():
  for pattern in patterns:
   for match in re.finditer(pattern,text):
    if any(n['span'][0]<=match.start()<n['span'][1] or match.start()<=n['span'][0]<match.end() for n in negatives):continue
    begin=max(text.rfind('.',0,match.start()),text.rfind(';',0,match.start()))+1
    ends=[n for n in [text.find('.',match.end()),text.find(';',match.end())] if n>=0];end=min(ends) if ends else len(text)
    item={'route':route,'span':list(match.span()),'text':match.group()}
    if re.search(r'\b(?:if|may|might|could|unless)\b',text[begin:end]):conditional.append(item)
    else:positives.append(item)
 pos=sorted({x['route'] for x in positives});neg=sorted({x['route'] for x in negatives});overlap=sorted(set(pos)&set(neg))
 status='conflicting' if overlap else 'explicit' if len(pos)==1 else 'unresolved'
 return {'positive_routes':pos,'excluded_routes':neg,'conflicting_routes':overlap,'eligible_routes':pos if status=='explicit' else [],'status':status,'positive_assertions':positives,'negative_assertions':negatives,'conditional_assertions':conditional,'qualified_negative_assertions':qualified}
def assess(text):
 x=extract(text);return x['positive_routes'],x['excluded_routes']
def controls():
 cases=[('For intravenous use. Should not be administered as an intravenous push or bolus.',['IV'],[],'explicit'),('For intravenous use. Not for intravenous bolus.',['IV'],[],'explicit'),('For oral use.',['O'],[],'explicit'),('Intravenous use.',['IV'],[],'explicit'),('For subcutaneous injection only.',['SC'],[],'explicit'),('Not for intravenous use.',[],['IV'],'unresolved'),('Not intended for intravenous administration.',[],['IV'],'unresolved'),('Not recommended for intravenous use.',[],['IV'],'unresolved'),('Intravenous use is not recommended.',[],['IV'],'unresolved'),('Never for oral use.',[],['O'],'unresolved'),('No intravenous use.',[],['IV'],'unresolved'),('Do not administer intravenously.',[],['IV'],'unresolved'),('Should not be administered via an intravenous infusion.',[],['IV'],'unresolved'),('Patients may receive intravenous or subcutaneous formulations.',[],[],'unresolved'),('For intravenous use if indicated.',[],[],'unresolved'),('Intravenous use may be considered.',[],[],'unresolved'),('For subcutaneous injection only. Not intended for intravenous administration.',['SC'],['IV'],'explicit'),('Not intended for subcutaneous administration and should be administered via an intravenous infusion only.',['IV'],['SC'],'explicit'),('For intravenous use. Not intended for intravenous administration.',['IV'],['IV'],'conflicting'),('Not for oral use. For oral use.',['O'],['O'],'conflicting'),('For oral use. For subcutaneous injection only.',['O','SC'],[],'unresolved'),('Not only for intravenous use.',['IV'],[],'explicit')]
 out=[]
 for text,pos,neg,status in cases:
  observed=extract(text);assert (observed['positive_routes'],observed['excluded_routes'],observed['status'])==(pos,neg,status),(text,observed)
  assert observed['status']=='explicit' or not observed['eligible_routes']
  out.append({'input':text,'expected':{'positive_routes':pos,'excluded_routes':neg,'status':status},'observed':observed})
 return out
if __name__=='__main__':print('Passed',len(controls()),'route assertion controls.')
