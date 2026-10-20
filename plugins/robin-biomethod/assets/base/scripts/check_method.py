#!/usr/bin/env python3
"""Public output-contract check, available to every drafting worker (no hidden answers)."""
import ast
from decimal import Decimal
import json
from pathlib import Path
import re
import sys

p=Path(sys.argv[1] if len(sys.argv)>1 else 'output/method.json')
errors=[]
def arithmetic(expression):
    def visit(n):
        if isinstance(n,ast.Expression):return visit(n.body)
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):return Decimal(str(n.value))
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return visit(n.operand)*(-1 if isinstance(n.op,ast.USub) else 1)
        if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub,ast.Mult,ast.Div)):
            a,b=visit(n.left),visit(n.right)
            return a+b if isinstance(n.op,ast.Add) else a-b if isinstance(n.op,ast.Sub) else a*b if isinstance(n.op,ast.Mult) else a/b
        raise ValueError('expression requires numbers and + - * / only; put units in assumptions')
    return visit(ast.parse(expression,mode='eval'))
try:
    data=json.loads(p.read_text())
    goal=json.loads(Path('source/goal.json').read_text())
    registry=json.loads(Path('source/registry.json').read_text())
    cards=json.loads(Path('source/method_cards.json').read_text())
    routes={c['id']:c for c in cards}
    lines={}
    for doc in registry['documents']:
        for line in Path('source',doc['text_file']).read_text().splitlines():
            m=re.match(r'\[([^\]]+)\]\s*(.*)',line)
            if m:lines[(doc['id'],m[1])]=m[2]
    for key in ('schema_version','material','status','target_assessment','evidence_limitations','uncertainties','candidate_methods','constraint_assessments','validation_experiments'):
        if key not in data:errors.append('missing '+key)
    if data.get('material')!=goal['material']:errors.append('material mismatch')
    if data.get('status') not in ('candidate_unvalidated','draft_missing_evidence'):errors.append('invalid method status')
    for m in data.get('candidate_methods',[]):
        for key in ('id','route_id','inputs','steps','checkpoints','characterization','gaps'):
            if key not in m:errors.append('method missing '+key)
        if m.get('route_id') not in routes:errors.append('unknown route_id');continue
        for s in m.get('steps',[]):
            for param in s.get('parameters',[]):
                origin=param.get('origin')
                if origin not in ('reported','calculated','proposed','unknown'):errors.append('invalid parameter origin')
                if origin=='calculated':
                    try:
                        expected=arithmetic(param.get('expression'));value=Decimal(str(param.get('value')))
                        if not expected.is_finite() or not value.is_finite() or abs(expected-value)>max(Decimal('0.000001'),abs(expected)*Decimal('0.000001')):errors.append('arithmetic result mismatch')
                    except (ValueError,TypeError,SyntaxError,ArithmeticError):errors.append('invalid arithmetic: use numeric + - * / expression, no units or equals sign')
                if origin=='reported' and not any(x.get('name')==param.get('name') and x.get('value')==param.get('value') and x.get('unit')==param.get('unit') for x in routes[m['route_id']]['parameters']):errors.append('reported value/unit/name not in frozen card: '+str(param.get('name')))
                if origin in ('reported','calculated') and not param.get('evidence'):errors.append('missing evidence')
                for c in param.get('evidence',[]):
                    if not c.get('quote') or c['quote'] not in lines.get((c.get('document'),c.get('locator')),''):errors.append('invalid exact source quote')
                if origin=='unknown' and (param.get('value') is not None or not param.get('reason') or not param.get('uncertainty_id')):errors.append('unknown must remain null with reason and uncertainty_id')
                if origin=='proposed' and (not param.get('rationale') or not param.get('uncertainty_id')):errors.append('proposal needs rationale and uncertainty link')
    critical={u['id'] for u in data.get('uncertainties',[]) if u.get('importance')=='critical'}
    covered=set()
    for e in data.get('validation_experiments',[]):
        covered.update(e.get('uncertainty_ids',[]))
        for key in ('id','method_ids','uncertainty_ids','hypothesis','controls','independent_batches','technical_repeats','sample_size_rationale','sampling','readouts','predicted_result','falsification','decision_rule'):
            if key not in e or e[key] in ('',None,[]):errors.append('experiment missing '+key)
        for r in e.get('readouts',[]):
            for key in ('metric','method','unit','acceptance','acceptance_basis'):
                if not r.get(key):errors.append('readout missing '+key)
    if not critical.issubset(covered):errors.append('critical uncertainties without discriminating experiments: '+', '.join(sorted(critical-covered)))
except (ValueError,KeyError,TypeError,OSError) as exc:errors.append(str(exc))
print(json.dumps(dict(valid=not errors,errors=errors,scope='public schema/provenance check; not scientific validation'),ensure_ascii=False,indent=2))
raise SystemExit(1 if errors else 0)
