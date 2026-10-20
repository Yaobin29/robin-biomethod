"""One deterministic entry point: goal -> literature -> extraction -> original Harness2."""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
from types import SimpleNamespace
from robinharness.runtime import Budget,CodexRunner,POLICY,dump,fingerprint,state_root,safe_relative
from robinharness.cli import optimize
from .research import search,collect,merge_collections,now
from .workflow import PLUGIN,read,validate_goal,source_index,prepare
from .execution import export_execution

DEFAULTS=dict(session_limit=16,minutes=45,k=1,model='codex-default',search_limit=8,max_sources=3)
STAGES=('intake','discovery','screening','full_text','method_extraction','freeze','harness2','delivery')


def settings(overrides=None):
    result=dict(DEFAULTS)
    path=state_root()/'settings.json'
    if path.exists():result.update(read(path))
    result.update({k:v for k,v in (overrides or {}).items() if v is not None})
    if type(result['session_limit']) is not int or result['session_limit']<1:
        raise ValueError('session_limit must be a positive integer.')
    if not isinstance(result['minutes'],(int,float)) or isinstance(result['minutes'],bool) or not math.isfinite(result['minutes']) or result['minutes']<=0:
        raise ValueError('minutes must be finite and positive.')
    if type(result['k']) is not int or result['k'] not in (1,2,3):raise ValueError('k must be1,2or3.')
    if not 1<=result['search_limit']<=25 or not 1<=result['max_sources']<=5:
        raise ValueError('search_limit must be1..25; max_sources must be1..5.')
    return result


def configure(overrides):
    config=settings(overrides);dump(state_root()/'settings.json',config)
    return dict(status='configured',settings=config,model_calls=0)


def minimum_sessions(k=1,provided_bundle=False):
    # Upstream:4k executions +3k editors + reflection + selector when k>1.
    return 7*k+1+int(k>1)+1+int(not provided_bundle)


def job_status(root):
    root=Path(root)
    data=read(root/'workflow.json')
    if (root/'budget.json').exists():
        budget=read(root/'budget.json')
        data['budget']=dict(max_sessions=budget['max_sessions'],sessions_attempted=len(budget['sessions']),
                            current_sessions=[dict(label=s['label'],state=s['state']) for s in budget['sessions']],
                            remaining_wall_seconds=max(0,int(budget['deadline']-time.time())))
    return data


class Journal:
    def __init__(self,root,config):
        self.root=root
        self.data=dict(schema_version=1,product='RobinBioMethod',mode='full-harness',status='running',
                       created=now(),settings=config,stages={s:dict(state='pending') for s in STAGES},
                       harness2_executed=False,workflow_complete=False,errors=[],scientific_performance='not experimentally tested')
        self.save()
    def save(self):
        self.data['updated']=now();dump(self.root/'workflow.json',self.data)
    def step(self,name,state,**detail):
        self.data['current_stage']=name
        self.data['stages'][name].update(state=state,updated=now(),**detail)
        self.save()
        print(json.dumps(dict(event='workflow.stage',stage=name,state=state),ensure_ascii=False),flush=True)


def model_json(runner,source,out,mission,label,validator=None):
    """One bounded format repair, sharing the SAME budget as all Harness2 sessions."""
    errors=[]
    for attempt in (1,2):
        with tempfile.TemporaryDirectory(prefix='biomethod-preparation-') as td:
            ws=Path(td);shutil.copytree(source,ws/'source');(ws/'output').mkdir();(ws/'AGENTS.md').write_text(POLICY)
            before=fingerprint(ws/'source')
            instruction=mission+'\nWrite only output/result.json. Source files are immutable. Finish by reopening and validating the JSON.\n'
            if errors:instruction+='Previous output failed validation: '+errors[-1]+'. Correct it using the ORIGINAL source; do not invent missing evidence.\n'
            runner.run(ws,instruction,f'{label}.a{attempt}')
            if before!=fingerprint(ws/'source'):raise ValueError('Preparation worker changed immutable sources.')
            try:
                result=read(ws/'output/result.json')
                if validator:validator(result)
                dump(out,result);return result
            except (ValueError,TypeError,KeyError,OSError) as exc:errors.append(str(exc))
    raise ValueError('Structured preparation failed after one repair: '+'; '.join(errors))


SCREEN='''Read source/goal.json and source/search.json. Select up to {limit} relevant primary method papers
from the exact search results with an available PMCID. Use target/material/assay fit rather than prestige.
Do not select reviews as procedural proof if primary method papers are available.
Return {{"selected":[{{"pmcid":"PMC...","reason":"bounded relevance"}}],"limitations":["coverage gaps"]}}.
This is metadata/abstract screening only, NOT a full-text method assessment. If nothing fits return selected:[] with reasons.'''
EXTRACT='''Read source/goal.json, source/registry.json and the numbered registered document files.
Read source/method-contract.txt for the final artifact contract. Extract at most TWO coherent synthesis routes
from relevant primary full-text methods; do not make a card from an abstract or a review's cited recipe.
Return one JSON object:
{
 "method_cards":[{"id":"route-id","document":"registered document id","name":"route name",
 "parameters":[{"name":"consistent parameter name","value":null,"unit":"unit","evidence":[{"document":"same document id","locator":"exact L...","quote":"exact short substring"}],"missing_reason":"required only when value is null"}],
 "limitations":["source/transfer/missing conditions"]}],
 "profile":{"id":"material-specific-task-profile","checks":["checkable material/assay/transfer rules, no invented numerical recipe"]},
 "literature_review":[{"document":"id","why":"relevance to goal","how":"source's actual method","what":"observed result and limits","method_evidence":[{"document":"id","locator":"L...","quote":"exact substring"}]}],
 "source_gaps":["supplements or referenced protocols still needed"]
}
Use about6-10 decisive parameters per route; include precursor identity, concentration/basis, feed,
medium/pH, temperature/time and purification when applicable. Unknown conditions stay null.
Each reported value must be supported by its own quoted source; preserve exact number/unit semantics.
Do not combine different precursor types, assays or route conditions. State when a source's target
is not the user's target. Mark missing tolerance/equipment/scale decisions as gaps, never fill them.
Keep suggestions/hypotheses distinct from observations. Expose target-specific calibration and minimum
validation needs in profile checks. A complete paper need not contain a complete executable procedure.
If no usable method exists, return method_cards:[] and explicit source_gaps; do not fabricate a route.'''


def run_design(goal_path,*,queries=None,bundle=None,run_dir=None,overrides=None,dry_run=False,runner_factory=None,prepared_from=None):
    if prepared_from:
        return retry_prepared(goal_path,prepared_from,run_dir=run_dir,overrides=overrides,dry_run=dry_run,runner_factory=runner_factory)
    cfg=settings(overrides);goal=read(goal_path);validate_goal(goal)
    minimum=minimum_sessions(cfg['k'],bool(bundle))
    if cfg['session_limit']<minimum:
        raise ValueError(f'This full workflow needs at least{minimum}model sessions before repairs/holdouts; raise the limit or choose an explicit draft-only request. No model call was made.')
    if dry_run:
        return dict(status='planned_not_executed',workflow_complete=False,harness2_executed=False,
                    minimum_sessions=minimum,settings=cfg,stages=list(STAGES),model_calls=0)
    root=Path(run_dir).expanduser().resolve() if run_dir else state_root()/'jobs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    root.mkdir(parents=True,exist_ok=False)
    journal=Journal(root,cfg);budget=Budget(root/'budget.json',cfg['session_limit'],cfg['minutes'])
    dump(root/'goal.json',goal)
    dump(root/'request.json',dict(goal_sha256=hashlib.sha256((root/'goal.json').read_bytes()).hexdigest(),queries=queries or [],provided_bundle=bool(bundle),settings=cfg))
    runner=None
    try:
        journal.step('intake','completed',goal='goal.json',unresolved=goal.get('unknown_fields',[]),assumptions=goal.get('assumption_notes',[]))
        if bundle:
            journal.step('discovery','completed_external_input',note='Using an explicitly supplied registered collection; no native search claimed.')
            journal.step('screening','completed_external_input',note='Caller selected sources; provenance and access still checked.')
            journal.step('full_text','running')
            merge_collections([Path(bundle)],root/'evidence')
            journal.step('full_text','completed',documents=len(read(root/'evidence/registry.json')['documents']))
        else:
            journal.step('discovery','running')
            actual_queries=queries or [goal.get('search_query') or f'"{goal["material"]}" AND (synthesis OR fabrication OR modification)']
            combined=dict(schema_version=1,queries=[],results=[],coverage='bounded public literature discovery, not systematic review')
            seen=set()
            for query in actual_queries:
                result=search(query,cfg['search_limit'])
                combined['queries'].append(result)
                for item in result['results']:
                    key=item.get('doi') or item.get('pmcid') or item.get('url')
                    if key not in seen:combined['results'].append(item);seen.add(key)
            dump(root/'search.json',combined)
            if not any(x.get('pmcid') for x in combined['results']):raise ValueError('No full-text PMCID candidates found. Supply a registered source collection or revise the query; no draft substituted.')
            journal.step('discovery','completed',records=len(combined['results']),record='search.json')
            runner=(runner_factory or CodexRunner)(budget,root/'audit',cfg['model'])
            screening_source=root/'screening-source';screening_source.mkdir()
            shutil.copy2(root/'goal.json',screening_source/'goal.json');shutil.copy2(root/'search.json',screening_source/'search.json')
            allowed={x['pmcid'] for x in combined['results'] if x.get('pmcid')}
            def check_screen(data):
                selected=data['selected']
                if not isinstance(selected,list) or len(selected)>cfg['max_sources']:raise ValueError('Invalid source selection size.')
                ids=[x['pmcid'] for x in selected]
                if len(ids)!=len(set(ids)) or not set(ids).issubset(allowed) or any(not x.get('reason') for x in selected):raise ValueError('Selection invented an identifier or omitted relevance.')
            journal.step('screening','running')
            screen=model_json(runner,screening_source,root/'screening.json',SCREEN.format(limit=cfg['max_sources']),'screening',check_screen)
            if not screen['selected']:raise ValueError('Screening found no relevant methods; inspect screening.json.')
            journal.step('screening','completed',record='screening.json')
            journal.step('full_text','running')
            collected=collect([x['pmcid'] for x in screen['selected']],root/'evidence',root/'search.json')
            if not collected['documents']:raise ValueError('Full text acquisition failed: '+json.dumps(collected['errors']))
            journal.step('full_text','completed_with_gaps' if collected['errors'] else 'completed',**collected)
        if runner is None:runner=(runner_factory or CodexRunner)(budget,root/'audit',cfg['model'])
        extraction_source=root/'extraction-source';shutil.copytree(root/'evidence',extraction_source)
        shutil.copy2(root/'goal.json',extraction_source/'goal.json');shutil.copy2(PLUGIN/'assets/task-prompt.txt',extraction_source/'method-contract.txt')
        def check_extraction(data):
            if not isinstance(data.get('method_cards'),list) or not isinstance(data.get('profile',{}).get('checks'),list):raise ValueError('Invalid cards/profile contract.')
            if not data['method_cards']:return
            check=root/'extraction-check';check.mkdir(exist_ok=True)
            # Check against the same trusted goal/registered source index as prepare.
            for filename in ('goal.json','registry.json'):
                shutil.copy2(extraction_source/filename,check/filename)
            if not (check/'documents').exists():shutil.copytree(extraction_source/'documents',check/'documents')
            dump(check/'method_cards.json',data['method_cards']);dump(check/'profile.json',data['profile'])
            from .workflow import validate_task_source,check_cites
            validate_task_source(check)
            docs,lines=source_index(check)
            review=data.get('literature_review',[])
            if not isinstance(review,list) or not review or any(not isinstance(x,dict) or x.get('document') not in docs or not all(isinstance(x.get(k),str) and x[k].strip() for k in ('why','how','what')) or not check_cites(x.get('method_evidence'),docs,lines) or any(c.get('document')!=x['document'] for c in x.get('method_evidence',[])) for x in review):raise ValueError('3W method review requires locatable full-text evidence for its own document.')
        journal.step('method_extraction','running')
        extracted=model_json(runner,extraction_source,root/'extraction.json',EXTRACT,'method-extraction',check_extraction)
        if not extracted['method_cards']:raise ValueError('No source-grounded synthesis route extracted: '+json.dumps(extracted.get('source_gaps',[])))
        dump(root/'method-cards.json',extracted['method_cards']);dump(root/'profile.json',extracted['profile'])
        journal.step('method_extraction','completed',record='extraction.json',routes=len(extracted['method_cards']))
        journal.step('freeze','running')
        prepare(root/'goal.json',root/'evidence',root/'method-cards.json',root/'task',root/'profile.json')
        journal.step('freeze','completed',task='task/task.json',source_hash=fingerprint(root/'task/source'))
        finish_core(root,journal,budget,runner,cfg)
    except Exception as exc:
        current=journal.data.get('current_stage','intake')
        journal.step(current,'failed',error=str(exc))
        journal.data.update(status='incomplete',workflow_complete=False)
        journal.data['errors'].append(str(exc))
        journal.data['recovery']='Inspect failed stage; correct input/network/account condition and explicitly start a new bounded run. Preserve this job; never present a chat draft as full Harness2 output.'
    finally:
        journal.data['model_sessions_attempted']=len(budget.data['sessions'])
        journal.data['usage']={key:sum(s.get('usage',{}).get(key,0) for s in budget.data['sessions']) for key in ('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens')}
        journal.data['cost_usd']=None;journal.save()
    return dict(status=journal.data['status'],workflow_complete=journal.data['workflow_complete'],harness2_executed=journal.data['harness2_executed'],
                job=str(root),workflow=str(root/'workflow.json'),method=str(root/'candidate-method.md') if (root/'candidate-method.md').exists() else None,
                model_sessions_attempted=journal.data['model_sessions_attempted'],errors=journal.data['errors'])

def finish_core(root,journal,budget,runner,cfg):
    remaining=len(budget.data['sessions'])+7*cfg['k']+1+int(cfg['k']>1)
    if remaining>cfg['session_limit']:raise ValueError('Remaining shared budget cannot finish original Harness2; preparation preserved. No ordinary method draft substituted.')
    journal.step('harness2','running',expected_stages=['baseline','INV','DOM','AGG','selection','reflection'])
    args=SimpleNamespace(task=str(root/'task/task.json'),run_dir=str(root/'harness'),k=cfg['k'],mode='parallel',
                         session_limit=cfg['session_limit'],minutes=cfg['minutes'],model=cfg['model'],holdout=[],learning_task=None,library_dir=None)
    report,harness=optimize(args,budget=budget,runner=runner)
    proof=export_execution(harness,root/'budget.json',root/'audit')
    journal.data['harness2_executed']=proof.get('core_executed',False)
    if proof.get('core_executed') and not proof['verified']:
        from .repair import repair_delivery
        journal.step('delivery','running',mode='post-core-contract-repair')
        proof=repair_delivery(root,runner_factory=lambda b,a,m: runner)
        journal.data['delivery_repair']='harness/delivery-repair/receipt.json'
    if not proof['verified']:
        failures=[x.get('error') or x['state']+': '+x['label'] for x in budget.data['sessions'] if x['state']!='ok']
        raise ValueError('Full Harness2 completion not verified; inspect harness/execution-evidence.json and stage outputs. '+ '; '.join(report.get('errors',[])+failures))
    journal.step('harness2','completed',evidence='harness/execution-evidence.json')
    journal.step('delivery','running')
    write_literature_review(root)
    for name in ('candidate-method.md','execution-report.md','stage-comparison.json','execution-evidence.json'):
        shutil.copy2(harness/name,root/name)
    shutil.copytree(harness/'stage-methods',root/'stage-methods',dirs_exist_ok=True)
    journal.step('delivery','completed',method='candidate-method.md',process='execution-report.md',comparisons='stage-comparison.json')
    journal.data.update(status='completed',workflow_complete=True)


def retry_prepared(goal_path,previous,*,run_dir=None,overrides=None,dry_run=False,runner_factory=None):
    """Reuse verified preparation, never resume/mutate a partly executed upstream tree."""
    previous=Path(previous).resolve();old=read(previous/'workflow.json')
    cfg=settings(overrides);goal=read(goal_path);validate_goal(goal)
    if goal!=read(previous/'goal.json'):raise ValueError('Recovery goal differs from frozen goal.')
    freeze=old['stages']['freeze']
    from .workflow import validate_task_source
    validate_task_source(previous/'task/source')
    if freeze.get('state')!='completed' or freeze.get('source_hash')!=fingerprint(previous/'task/source'):
        raise ValueError('No intact frozen preparation to reuse.')
    prior_budget=read(previous/'budget.json')
    spent=len(prior_budget['sessions'])
    consumed_minutes=max(0,(old.get('ended_at',0) or max([prior_budget['started']]+[x.get('ended',x['started']) for x in prior_budget['sessions']]))-prior_budget['started'])/60
    if cfg['minutes']>old['settings']['minutes']-consumed_minutes:
        raise ValueError('Recovery time exceeds remaining prior wall allowance.')
    available=old['settings']['session_limit']-spent
    if cfg['session_limit']>available:raise ValueError('Recovery limit exceeds remaining prior session allowance.')
    minimum=7*cfg['k']+1+int(cfg['k']>1)
    if cfg['session_limit']<minimum:raise ValueError('Recovery needs sufficient remaining core budget.')
    if dry_run:return dict(status='planned_not_executed',workflow_complete=False,harness2_executed=False,model_calls=0,minimum_sessions=minimum)
    root=Path(run_dir).resolve() if run_dir else state_root()/'jobs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    root.mkdir(parents=True,exist_ok=False);journal=Journal(root,cfg)
    budget=Budget(root/'budget.json',cfg['session_limit'],cfg['minutes'])
    try:
        for name in ('goal.json','extraction.json','method-cards.json','profile.json'):
            shutil.copy2(previous/name,root/name)
        shutil.copytree(previous/'task',root/'task')
        for stage in STAGES[:6]:
            journal.step(stage,'reused_verified_input',previous=str(previous),note='Preparation reused; native search and model extraction are not repeated.')
        journal.data['recovery_from']=str(previous)
        journal.data['prior_attempts']=spent+old.get('prior_attempts',0)
        runner=(runner_factory or CodexRunner)(budget,root/'audit',cfg['model'])
        finish_core(root,journal,budget,runner,cfg)
    except Exception as exc:
        journal.step(journal.data.get('current_stage','intake'),'failed',error=str(exc))
        journal.data.update(status='incomplete',workflow_complete=False)
        journal.data['errors'].append(str(exc))
    finally:
        journal.data['model_sessions_attempted']=len(budget.data['sessions'])
        journal.data['usage']={key:sum(x.get('usage',{}).get(key,0) for x in budget.data['sessions']) for key in ('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens')}
        journal.data['cost_usd']=None;journal.save()
    return dict(status=journal.data['status'],workflow_complete=journal.data['workflow_complete'],harness2_executed=journal.data['harness2_executed'],job=str(root),model_sessions_attempted=journal.data['model_sessions_attempted'],errors=journal.data['errors'])

def write_literature_review(root):
    extracted=read(root/'extraction.json')
    records=read(root/'task/source/registry.json')['documents']
    urls={d['id']:d['url'] for d in records}
    today=datetime.now(timezone.utc).date().isoformat()
    lines=['---','id: output-artifact/biomethod/literature-'+hashlib.sha256(str(root).encode()).hexdigest()[:12],
           'type: output-artifact','title: "Source-grounded 3W method review"','status: generated','version: v1',
           'created: '+today,'updated: '+today,'tags: [research, biomethod, literature]','---','',
           '# Literature evidence','', 'Bounded source selection; not a systematic review or experimental validation.','']
    for entry in extracted.get('literature_review',[]):
        did=entry['document'];lines+=['## '+did,'',urls.get(did,''),'']
        for field in ('why','how','what'):lines+=['**'+field.upper()+'**: '+entry[field],'']
        for c in entry['method_evidence']:lines+=['> '+c['quote'],'',c['document']+' / '+c['locator'],'']
    lines+=['## Remaining source gaps','']+['- '+gap for gap in extracted.get('source_gaps',[])]
    (root/'literature-review.md').write_text('\n'.join(lines)+'\n')
