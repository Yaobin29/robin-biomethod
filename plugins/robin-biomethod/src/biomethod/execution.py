"""Verify real Harness2 execution from CLI traces, stage ledger and deliverables."""
from pathlib import Path
from datetime import date
import hashlib
import json
from .workflow import read
from .validation import assess
from .reporting import render
from robinharness.runtime import dump, fingerprint


def _execution_evidence(run, budget_path=None, audit_dir=None):
    run=Path(run).resolve()
    if not (run/'report.json').exists():
        return dict(verified=False,core_executed=False,status='not_executed',reason='No Harness2 report exists.',stages=[])
    report=read(run/'report.json')
    if budget_path is None and run.name=='harness' and (run.parent/'workflow.json').is_file():budget_path=run.parent/'budget.json'
    budget=read(budget_path) if budget_path else report.get('budget',{})
    audit=Path(audit_dir) if audit_dir else (run.parent/'audit' if run.name=='harness' and (run.parent/'workflow.json').is_file() else run/'audit')
    actual=[]
    for index,s in enumerate(budget.get('sessions',[])):
        path=audit/f'{index:03d}.jsonl';ok=False
        if s.get('state')=='ok' and s.get('transport')=='codex_cli' and path.is_file():
            try:
                raw=path.read_bytes();events=[json.loads(x) for x in raw.decode().splitlines() if x.strip()]
                ok=(hashlib.sha256(raw).hexdigest()==s.get('audit_sha256') and
                    any(e.get('type')=='turn.completed' for e in events) and
                    any(e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message' for e in events))
            except (ValueError,UnicodeError):pass
        actual.append(dict(index=index,label=s.get('label'),state=s.get('state'),verified_transport=ok))
    result=report.get('upstream_result',{})
    token='agg' if report.get('method',{}).get('mode','parallel')=='parallel' else 'seq'
    mode=result.get('modes',{}).get(token,{});ledger=mode.get('ledger',{})
    selection=result.get('selections',{}).get(token,{});task_id=result.get('task_id');stages=[]
    for label in ledger.get('rollouts',[]):
        paths=[p for p in (run/'primary/executions').rglob(f'{label}/output/method.json') if task_id in p.parts]
        calls=[s for s in actual if s['verified_transport'] and str(s['label']).startswith('execute:') and str(s['label']).endswith(f'/{task_id}/{label}')]
        kind='baseline' if label.startswith('base') else 'INV' if label.startswith('inv') else 'DOM' if label.startswith('dom') else 'AGG'
        artifact=paths[0] if len(paths)==1 else None
        integrity=False
        if artifact and (artifact.parent.parent/'execution.json').is_file():
            receipt=read(artifact.parent.parent/'execution.json')
            integrity=(receipt.get('output_hash')==fingerprint(artifact.parent) and receipt.get('source_hash')==fingerprint(run/'frozen/source') and receipt.get('audit_index') in [s['index'] for s in calls])
        stages.append(dict(label=label,kind=kind,artifact=str(artifact) if artifact else None,executed=bool(calls and artifact and integrity),integrity_verified=integrity,session_indices=[s['index'] for s in calls]))
    edits=[]
    for stage in mode.get('stages',[]):
        calls=[s for s in actual if s['verified_transport'] and str(s['label']).startswith(stage['label']+'.')]
        edits.append(dict(label=stage['label'],dimension=stage.get('dim'),executed=bool(calls),kept_base=stage.get('kept_base'),notes=stage.get('notes'),session_indices=[s['index'] for s in calls]))
    k=report.get('method',{}).get('k',1)
    selector=selection.get('trivial') is True if k==1 else any(s['verified_transport'] and str(s['label']).startswith('select.') for s in actual)
    reflection=any(s['verified_transport'] and str(s['label']).startswith('experience.') for s in actual)
    core=(result.get('status')=='ok' and len(stages)==4*k and all(s['executed'] for s in stages) and len(edits)==3*k and all(s['executed'] for s in edits) and bool(selector) and reflection)
    chosen=next((s for s in stages if s['label']==selection.get('chosen_label')),None)
    assessment=assess(run/'frozen/source',Path(chosen['artifact'])) if chosen and chosen['artifact'] else dict(valid=False,errors=['missing selected method'])
    delivery=Path(chosen['artifact']) if chosen and chosen['artifact'] else None
    repaired=False;delivery_assessment=assessment
    repair=run/'delivery-repair'
    if delivery and (repair/'receipt.json').is_file():
        receipt=read(repair/'receipt.json');candidate=repair/'method.json'
        calls=[x for x in actual if x['verified_transport'] and str(x['label']).startswith('delivery-repair.')]
        repaired=(candidate.is_file() and (repair/'patch.json').is_file() and receipt.get('patch_sha256')==hashlib.sha256((repair/'patch.json').read_bytes()).hexdigest() and receipt.get('original_sha256')==hashlib.sha256(delivery.read_bytes()).hexdigest()
                  and receipt.get('output_sha256')==hashlib.sha256(candidate.read_bytes()).hexdigest()
                  and receipt.get('audit_index') in [x['index'] for x in calls])
        if repaired:
            delivery=candidate;delivery_assessment=assess(run/'frozen/source',candidate)
    verified=bool(core and report.get('status')=='completed' and delivery_assessment['valid'])
    return dict(verified=verified,core_executed=bool(core),status='completed' if verified else 'incomplete',upstream=report.get('upstream'),task=task_id,
                stages=stages,rule_edits=edits,selector=dict(executed=bool(selector),mode='single-final delivery without comparative inference' if k==1 else 'comparative model selection'),
                reflection_executed=reflection,experience_saved=selection.get('experience'),selected=selection.get('chosen_label'),selected_assessment=assessment,delivery_assessment=delivery_assessment,delivery_artifact=str(delivery) if delivery else None,delivery_repair_executed=repaired,sessions=actual,
                model_sessions_attempted=len(actual),model_sessions_verified=sum(s['verified_transport'] for s in actual),scientific_performance='not experimentally tested',
                completion_basis='Actual CLI traces + upstream ledger + stage artifacts + final document checks')


def execution_evidence(run, budget_path=None, audit_dir=None):
    """Corrupt or incomplete audit data can never become completion evidence."""
    try:
        return _execution_evidence(run, budget_path, audit_dir)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return dict(verified=False, core_executed=False, status='incomplete',
                    reason='Invalid execution evidence: '+str(exc), stages=[])


def stage_parameters(path):
    try:
        return parameter_map(read(path))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {}


def parameter_map(data):
    return {f"{m.get('route_id')}/{p.get('name')}":dict(value=p.get('value'),unit=p.get('unit'),origin=p.get('origin'))
            for m in data.get('candidate_methods',[]) for s in m.get('steps',[]) for p in s.get('parameters',[])}


def export_execution(run,budget_path=None,audit_dir=None):
    run=Path(run);proof=execution_evidence(run,budget_path,audit_dir);dump(run/'execution-evidence.json',proof)
    comparisons=[];base=next((s for s in proof['stages'] if s['kind']=='baseline' and s.get('artifact')),None)
    bp=stage_parameters(base['artifact']) if base else {}
    for stage in proof['stages']:
        if not stage.get('artifact'):continue
        path=Path(stage['artifact']);params=stage_parameters(path)
        changes=[dict(parameter=k,baseline=bp.get(k),candidate=params.get(k)) for k in sorted(bp.keys()|params.keys()) if bp.get(k)!=params.get(k)]
        rendered=run/'stage-methods'/f"{stage['label']}.md"
        try:assessment=render(run/'frozen/source',path,rendered)
        except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:assessment=dict(valid=False,errors=[str(exc)])
        comparisons.append(dict(label=stage['label'],kind=stage['kind'],executed=stage['executed'],artifact=stage['artifact'],rendered=str(rendered) if rendered.exists() else None,parameter_changes=changes,assessment=assessment))
    dump(run/'stage-comparison.json',dict(status=proof['status'],stages=comparisons,rule_edits=proof.get('rule_edits',[]),delivery_artifact=proof.get('delivery_artifact'),delivery_assessment=proof.get('delivery_assessment'),delivery_repair_executed=proof.get('delivery_repair_executed',False),scope='same-task stages; not independent heldout or wet-lab efficacy',recommended=False))
    selected=next((s for s in proof['stages'] if s['label']==proof.get('selected') and s.get('artifact')),None)
    if proof.get('delivery_artifact') and proof.get('delivery_assessment',{}).get('valid'):render(run/'frozen/source',Path(proof['delivery_artifact']),run/'candidate-method.md')
    lines=['---','id: output-artifact/biomethod/execution-'+hashlib.sha256(str(run.resolve()).encode()).hexdigest()[:12],'type: output-artifact',
           'title: "RobinBioMethod actual execution evidence"','status: generated','version: v1',f'created: {date.today().isoformat()}',f'updated: {date.today().isoformat()}',
           'tags: [output, research, biomethod]','---','','# Harness² 实际执行记录','',f"全流程验收：{proof['status']}。核心执行已核验：{proof.get('core_executed',False)}。",'',
           '| 阶段 | 实际执行 | 方法文件 | 相对基线参数变化数 |','| --- | --- | --- | --- |']
    for c in comparisons:
        link=f"[查看 {c['label']} 方法](stage-methods/{c['label']}.md)" if c['rendered'] else '无'
        lines.append(f"| {c['kind']} / {c['label']} | {c['executed']} | {link} | {len(c['parameter_changes'])} |")
    if proof.get('reason'):lines+=['','证据检查失败原因：'+proof['reason'],'']
    lines+=['','## 规则修改与合成决定','']
    for e in proof.get('rule_edits',[]):lines.append(f"- {e['label']} ({e['dimension']}): {e.get('notes') or 'no notes'}")
    lines+=['',f"最终交付：{proof.get('selected')}。",f"选择过程：{proof.get('selector',{}).get('mode')}。",'',
            f"经验反思已调用：{proof.get('reflection_executed',False)}；经验保存决定：{proof.get('experience_saved')}。",
            f"单独记录的交付文档修复：{proof.get('delivery_repair_executed',False)}；原始阶段输出保留。",
            'KEEP_BASE也是合法结果；参数未改变不代表未运行。须以execution-evidence.json和审计轨迹核对真实执行。',
            '本记录不证明合成效果、纯度或生物相容性；候选仍需科学审阅和实验验证。','']
    (run/'execution-report.md').write_text('\n'.join(lines))
    if proof.get('delivery_artifact') and proof.get('delivery_assessment',{}).get('valid'):
        from .html_report import render_job_report
        render_job_report(run,proof)
    return proof
