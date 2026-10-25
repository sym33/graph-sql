"""Finite, target-specific evidence contract. No medication assumptions."""
from dataclasses import dataclass
from typing import Mapping
ORDER = ('I', 'S', 'E', 'K', 'F', 'A')
EVALUATION_ORDER = ('I', 'S', 'E', 'K', 'A', 'F')
@dataclass(frozen=True)
class Judgment:
    status: str
    reason: str
    diagnostic: str

def judge(obligations: Mapping[str, bool]) -> Judgment:
    if set(obligations) != set(ORDER) or any(type(x) is not bool for x in obligations.values()):
        raise ValueError('Exactly six Boolean obligations are required')
    authenticated = all(obligations[k] for k in ('I','S','E'))
    diagnostic = ('AGREEMENT' if obligations['F'] else 'CONFLICT') if authenticated else 'UNAVAILABLE'
    for key in EVALUATION_ORDER:
        if not obligations[key]:
            return Judgment('CONTRADICTED' if key == 'F' else 'UNDETERMINED',key,diagnostic)
    return Judgment('VERIFIED','ALL',diagnostic)

def select(judgments: Mapping[str, Judgment]):
    selected = sorted(k for k,j in judgments.items() if j.status == 'VERIFIED')
    excluded = {k: {'status':j.status,'reason':j.reason} for k,j in sorted(judgments.items()) if j.status != 'VERIFIED'}
    return {'selected': selected,'excluded':excluded}
