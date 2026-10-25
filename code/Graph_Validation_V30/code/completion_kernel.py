"""Finite documentary completion, with conditional sharp single-field bounds.

No medication, provider, parser or database-engine dependencies.
Each query has a fixed option set and an existential set of source-field witnesses.
Distinct unrevealed fields vary independently within their admitted route domains.
"""
from itertools import combinations
from dataclasses import dataclass

@dataclass(frozen=True)
class Field:
    key: str
    possible: frozenset
    known: frozenset = frozenset()

@dataclass(frozen=True)
class Question:
    key: str
    fields: tuple
    options: frozenset

class Completion:
    def __init__(self, fields, questions, vocabulary):
        self.fields={f.key:f for f in fields}
        self.questions={q.key:q for q in questions}
        self.vocabulary=frozenset(vocabulary)
        assert all(f.possible and f.known<=f.possible for f in fields)
        assert all(len(set(q.fields))==len(q.fields) and set(q.fields)<=self.fields.keys() for q in questions)
        self.affected={k:tuple(sorted(q.key for q in questions if k in q.fields)) for k in self.fields}

    def path(self, field, options, overrides=None):
        f=self.fields[field];known=(overrides or {}).get(field,f.known)
        if not options:return 'U'
        if known:
            if known&options:return 'V'
            return 'C' if options<=self.vocabulary else 'U'
        if f.possible<=options:return 'V'
        if not options<=self.vocabulary:return 'U'
        return 'C' if f.possible.isdisjoint(options) else 'U'

    def state(self, question, overrides=None):
        q=self.questions[question];states=[self.path(f,q.options,overrides) for f in q.fields]
        return 'V' if 'V' in states else 'C' if states and all(s=='C' for s in states) else 'U'

    def states(self, overrides=None):
        return {k:self.state(k,overrides) for k in sorted(self.questions)}

    @staticmethod
    def completions(possible):
        xs=sorted(possible)
        return tuple(frozenset(c) for n in range(1,len(xs)+1) for c in combinations(xs,n))

    def bounds(self, field, overrides=None):
        overrides=dict(overrides or {})
        before={q:self.state(q,overrides) for q in self.affected[field]}
        unresolved={q for q,s in before.items() if s=='U'}
        outcomes=[]
        for value in self.completions(self.fields[field].possible):
            after={**overrides,field:value}
            resolved=tuple(sorted(q for q in unresolved if self.state(q,after)!='U'))
            outcomes.append((len(resolved),tuple(sorted(value)),resolved))
        low=min(outcomes);high=max(outcomes)
        return {'field':field,'minimum':low[0],'maximum':high[0],
                'affected_unresolved':len(unresolved),'worlds':len(outcomes),
                'minimum_witness_routes':list(low[1]),'minimum_witness_questions':list(low[2]),
                'maximum_witness_routes':list(high[1]),'maximum_witness_questions':list(high[2])}

    def ranking(self, fields, overrides=None):
        rows=[self.bounds(f,overrides) for f in fields]
        return sorted(rows,key=lambda x:(-x['minimum'],-x['maximum'],-x['affected_unresolved'],x['field']))
