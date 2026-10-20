"""Bounded post-core contract repair; original stage outputs remain immutable."""
from pathlib import Path
import copy
import hashlib
import shutil
import tempfile
from robinharness.runtime import Budget,CodexRunner,dump
from .workflow import PLUGIN,read
from .validation import assess


def without_expressions(data):
    if isinstance(data,dict):return {k:without_expressions(v) for k,v in data.items() if k!='expression'}
    if isinstance(data,list):return [without_expressions(x) for x in data]
    return data


def repair_delivery(job,runner_factory=None):
    from .execution import export_execution
    from .pipeline import model_json,write_literature_review
    job=Path(job).resolve();run=job/'harness'
    proof=export_execution(run,job/'budget.json',job/'audit')
    if not proof.get('core_executed'):raise ValueError('Delivery repair requires all original core stages already executed.')
    if proof['verified']:return proof
    stage=next(x for x in proof['stages'] if x['label']==proof['selected'])
    original=Path(stage['artifact']);before=read(original)
    out=run/'delivery-repair';out.mkdir(exist_ok=True)
    if (out/'method.json').exists():raise ValueError('Existing delivery repair preserved; inspect it instead of overwriting.')
    history=read(job/'workflow.json')
    if not (job/'workflow-before-delivery-repair.json').exists():dump(job/'workflow-before-delivery-repair.json',history)
    history['current_stage']='delivery';history['stages']['delivery']=dict(state='running',mode='post-core-contract-repair')
    dump(job/'workflow.json',history)
    budget=Budget(job/'budget.json');model=history['settings']['model']
    runner=(runner_factory or CodexRunner)(budget,job/'audit',model)
    with tempfile.TemporaryDirectory(prefix='biomethod-contract-') as td:
        source=Path(td)/'source';shutil.copytree(run/'frozen/source',source)
        shutil.copy2(original,source/'draft.json')
        dump(source/'contract-errors.json',proof['selected_assessment']['errors'])
        shutil.copy2(PLUGIN/'assets/task-prompt.txt',source/'method-contract.txt')
        shutil.copy2(PLUGIN/'assets/base/scripts/check_method.py',source/'public-checker.py')
        def materialize(patch):
            if not isinstance(patch,dict) or set(patch)-{'expressions','validation_experiments'}:
                raise ValueError('Contract repair changed original scientific content or unknown patch fields.')
            data=copy.deepcopy(before)
            for change in patch.get('expressions',[]):
                if set(change)!={'method_id','step','parameter','expression'}:raise ValueError('Invalid expression patch.')
                method=next(m for m in data['candidate_methods'] if m['id']==change['method_id'])
                if type(change['step']) is not int or type(change['parameter']) is not int or change['step']<0 or change['parameter']<0:raise ValueError('Invalid expression index.')
                param=method['steps'][change['step']]['parameters'][change['parameter']]
                if param['origin']!='calculated':raise ValueError('Only calculated expressions may be patched.')
                param['expression']=change['expression']
            if 'validation_experiments' in patch:data['validation_experiments']=patch['validation_experiments']
            return data
        def validator(patch):
            data=materialize(patch)
            expected=without_expressions(copy.deepcopy(before));actual=without_expressions(copy.deepcopy(data))
            expected.pop('validation_experiments',None);actual.pop('validation_experiments',None)
            if expected!=actual:raise ValueError('Contract repair changed original scientific content outside expressions/experiments.')
            checking=out/'checking.json';dump(checking,data)
            result=assess(run/'frozen/source',checking)
            if not result['valid']:raise ValueError('; '.join(result['errors']))
        mission='''Read source/draft.json, contract-errors.json and method-contract.txt, plus frozen source evidence.
Repair ONLY numeric arithmetic expression syntax and complete discriminating validation experiments
for every declared critical uncertainty. Preserve all original method parameters, values, units,
evidence, uncertainties, status, constraints and scientific claims. Keep missing target tolerance
unknown; experiments are proposals, never achieved results. Do not remove uncertainty or weaken checks.
Units belong in existing assumptions, never arithmetic expressions. Do not change source files.
User tolerance choices, equipment qualification and hazard approval are NOT experimental
outcomes. Carry these as explicit prerequisites/stop conditions of relevant experiments,
with the corresponding uncertainty IDs; do not invent an experiment that measures a preference
or claims approval. An unapproved condition stays blocked and unvalidated.
Write a compact output/result.json patch, NOT the complete method:
{"expressions":[{"method_id":"M1","step":0,"parameter":0,"expression":"numeric + - * / only"}],
 "validation_experiments":[the complete repaired experiment array]}
Indices are zero-based. Omit expressions when no arithmetic correction is needed. No other patch
fields are allowed. The controller applies this patch to the immutable draft and checks the result.'''
        try:
            patch=model_json(runner,source,out/'patch.json',mission,'delivery-repair',validator)
            dump(out/'method.json',materialize(patch))
        except Exception as exc:
            history['stages']['delivery']=dict(state='failed',error=str(exc),mode='post-core-contract-repair')
            history.update(status='incomplete',workflow_complete=False,model_sessions_attempted=len(read(budget.path)['sessions']))
            history.setdefault('errors',[]).append(str(exc));dump(job/'workflow.json',history)
            raise
    budget.data=read(budget.path)
    index=len(budget.data['sessions'])-1
    dump(out/'receipt.json',dict(original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
         output_sha256=hashlib.sha256((out/'method.json').read_bytes()).hexdigest(),patch_sha256=hashlib.sha256((out/'patch.json').read_bytes()).hexdigest(),audit_index=index,
         scope='post-core contract repair; original stage output retained'))
    proof=export_execution(run,job/'budget.json',job/'audit')
    if not proof['verified']:raise ValueError('Delivery repair transport or provenance not verified.')
    for name in ('candidate-method.md','execution-report.md','stage-comparison.json','execution-evidence.json'):
        shutil.copy2(run/name,job/name)
    shutil.copytree(run/'stage-methods',job/'stage-methods',dirs_exist_ok=True)
    write_literature_review(job)
    history=read(job/'workflow.json')
    history.setdefault('recovered_errors',[]).extend(history.get('errors',[]))
    history.update(status='completed',workflow_complete=True,harness2_executed=True,errors=[],current_stage='delivery',
        model_sessions_attempted=len(budget.data['sessions']),delivery_repair='harness/delivery-repair/receipt.json',
        usage={key:sum(x.get('usage',{}).get(key,0) for x in budget.data['sessions']) for key in ('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens')})
    history['stages']['harness2']['state']='completed'
    history['stages']['delivery']=dict(state='completed',note='Original AGG preserved; post-core contract repair separately audited.')
    dump(job/'workflow.json',history)
    return proof
