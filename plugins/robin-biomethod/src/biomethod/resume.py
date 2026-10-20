"""Resume ONLY a failed k1 final using pinned upstream selection/reflection primitives."""
from pathlib import Path
import math
import shutil
import time
from robinharness.runtime import Budget,CodexRunner,dump,fingerprint
from robinharness.engine import FileTaskAdapter,CodexProposer,validate_config,evaluate
from harness2.core import tree,selection
from harness2.core.spec import RunView
from .workflow import read
from .execution import export_execution


def resume_final(job,*,minutes,runner_factory=None):
    job=Path(job).resolve();run=job/'harness';report=read(run/'report.json')
    proof=export_execution(run,job/'budget.json',job/'audit')
    if report.get('method')!={'k':1,'mode':'parallel'}:raise ValueError('Final-only recovery supports parallel k1 only.')
    stages={s['label']:s for s in proof['stages']}
    if set(stages)!={'base1','inv1','dom1','agg1'} or not all(stages[x]['executed'] for x in ('base1','inv1','dom1')):
        raise ValueError('Final-only recovery needs three intact successful rollouts.')
    if stages['agg1'].get('artifact') or not all(x['executed'] for x in proof.get('rule_edits',[])) or len(proof.get('rule_edits',[]))!=3:
        raise ValueError('Recovery requires all three real rule proposals and a missing final artifact.')
    budget=Budget(job/'budget.json')
    sessions=budget.data['sessions']
    active_end=max([budget.data['started']]+[s.get('ended',s['started']) for s in sessions])
    used=active_end-budget.data.get('continuation_started',budget.data['started'])+budget.data.get('continued_active_seconds',0)
    # Caller may spend only the previously authorized cumulative time, excluding pauses.
    allowance=read(job/'workflow.json')['settings']['minutes']*60-used
    if not math.isfinite(minutes) or minutes<=0 or minutes*60>allowance+1:raise ValueError('Recovery time exceeds remaining job allowance.')
    if budget.data['max_sessions']-len(sessions)<2:raise ValueError('At least two remaining sessions are needed.')
    if any(s['state']=='running' for s in sessions):raise ValueError('An existing call is still running.')
    summary=next((run/'primary/runs').rglob('summary.json'));work=summary.parent
    final_tree=work/'harnesses/agg1'
    runner=(runner_factory or CodexRunner)(budget,job/'audit',report['model'])
    adapter=FileTaskAdapter(run/'frozen/task.json',run/'primary',runner)
    config=tree.read_tree(adapter.substrate.surface(),final_tree);validate_config(config)
    harvested=list((run/'editors/harvests').glob('*/agg1.a*'))
    if not any(tree.read_tree(adapter.substrate.surface(),p)==config for p in harvested):raise ValueError('Saved final harness differs from original AGG proposal.')
    history=job/'final-recovery-history';history.mkdir(exist_ok=False)
    for p in (run/'report.json',job/'workflow.json',job/'budget.json',summary):shutil.copy2(p,history/('upstream-summary.json' if p==summary else p.name))
    dump(history/'checkpoint.json',dict(source_hash=fingerprint(run/'frozen/source'),final_harness_hash=fingerprint(final_tree),remaining_minutes=minutes,prior_sessions=len(sessions)))
    budget.data['deadline']=time.time()+minutes*60;budget.data['continued_active_seconds']=used;budget.data['continuation_started']=time.time()
    dump(budget.path,budget.data)
    workflow=read(job/'workflow.json');workflow.update(status='running',current_stage='harness2')
    workflow['stages']['harness2']=dict(state='running',mode='resume-native-final-only');dump(job/'workflow.json',workflow)
    try:
        views={}
        for label in ('base1','inv1','dom1'):
            rd=Path(stages[label]['artifact']).parent.parent
            views[label]=RunView(label=label,run_id=read(rd/'execution.json')['run_id'],run_dir=rd,ok=True,delivered=True)
        run_id=views['base1'].run_id.rsplit('/',1)[0]+'/agg1'
        rd=adapter.execute(adapter.task_id,final_tree,run_id)
        views['agg1']=RunView(label='agg1',run_id=run_id,run_dir=rd,ok=True,delivered=adapter.delivered(rd))
        sel=selection.trivial_selection(adapter.task_id,1,'agg',{'agg1':views['agg1']},adapter=adapter,work_dir=work)
        if not sel.ok:raise ValueError(sel.error)
        selection.reflect_adoption(adapter.task_id,sel,views,adapter=adapter,prop=CodexProposer(runner,run/'editors'),work_dir=work,decisions={x['label']:x.get('notes','') for x in proof['rule_edits']})
        selected=dict(sel.to_dict(),chosen_run_dir=str(rd),chosen_tree_is_base=config==tree.read_tree(adapter.substrate.surface(),adapter.base_harness()),harness_fingerprint=fingerprint(final_tree))
        result=report['upstream_result'];result['selections']['agg']=selected;result.update(status='ok',errors=[])
        report.update(status='completed',errors=[],candidate=str(final_tree),candidate_hash=fingerprint(final_tree),upstream_result=result,budget=read(budget.path),recovery='Native final execution, trivial selection and reflection; preceding successful stages retained.')
        report['evaluations']=[dict(task=adapter.task_id,split='adaptation',base=evaluate(adapter,views['base1'].run_dir),candidate=evaluate(adapter,rd))]
        dump(run/'report.json',report);dump(summary,result)
        proof=export_execution(run,job/'budget.json',job/'audit')
        if not proof['core_executed']:raise ValueError('Original stage/transport completion still unverified.')
        if not proof['verified']:
            from .repair import repair_delivery
            proof=repair_delivery(job,runner_factory=lambda b,a,m: runner)
        else:
            from .pipeline import write_literature_review
            for name in ('candidate-method.md','execution-report.md','stage-comparison.json','execution-evidence.json'):shutil.copy2(run/name,job/name)
            shutil.copytree(run/'stage-methods',job/'stage-methods',dirs_exist_ok=True);write_literature_review(job)
        workflow=read(job/'workflow.json');workflow.update(status='completed',workflow_complete=True,harness2_executed=True,errors=[],current_stage='delivery')
        workflow['stages']['harness2']=dict(state='completed',mode='native-final-recovery')
        workflow['stages']['delivery']=dict(state='completed');dump(job/'workflow.json',workflow)
    except Exception as exc:
        workflow=read(job/'workflow.json');workflow.update(status='incomplete',workflow_complete=False)
        workflow['errors']=workflow.get('errors',[])+[str(exc)];workflow['stages']['harness2']=dict(state='failed',error=str(exc),mode='native-final-recovery')
        dump(job/'workflow.json',workflow)
    finally:
        workflow=read(job/'workflow.json');current=read(budget.path)
        workflow['model_sessions_attempted']=len(current['sessions'])
        workflow['usage']={key:sum(s.get('usage',{}).get(key,0) for s in current['sessions']) for key in ('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens')}
        dump(job/'workflow.json',workflow)
    return workflow
