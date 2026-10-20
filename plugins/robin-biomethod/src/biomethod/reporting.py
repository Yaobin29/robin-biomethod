"""Human-readable method packages and transparent stage comparison."""
from __future__ import annotations
from pathlib import Path
from datetime import date
import hashlib
from robinharness.runtime import dump
from .workflow import read
from .validation import assess


def render(source, artifact, out):
    if Path(out).suffix.lower() in ('.html', '.htm'):
        from .html_report import render_html
        return render_html(source, artifact, out)
    data = read(artifact);goal=read(Path(source)/'goal.json')
    lines = ["---", "id: output-artifact/biomethod/method-" + hashlib.sha256(str(out).encode()).hexdigest()[:12], "type: output-artifact",
             'title: "Candidate biomaterial method and minimal validation"', "status: generated", "version: v1",
             f"created: {date.today().isoformat()}", f"updated: {date.today().isoformat()}", "tags: [output, research, biomethod]", "---", "",
             "# 候选合成方法＋最小验证实验", "", f"材料：{data.get('material')}；状态：{data.get('status')}。",
             "", "本报告未证明合成效果、纯度、生物相容性或实验安全性。", "",
             "## 目标与证据边界", "", f"目标：{goal['target']['metric']} = {goal['target']['value']} ± {goal['target']['tolerance'] if goal['target']['tolerance'] is not None else '未确定'} {goal['target']['unit']}。",
             f"定义：{goal['target']['definition']}；测定：{goal['target']['assay']}。", "", f"规模：{goal['scale']['value']} {goal['scale']['unit']}；基准：{goal['scale']['basis']}。", ""]
    lines += ["- " + x for x in data.get('evidence_limitations', [])]
    for m in data.get('candidate_methods', []):
        lines += ["", f"## 方法 {m['id']}（来源路线 {m['route_id']}；{m.get('disposition', 'candidate_draft')}）", "", "原料与设备：" + "; ".join(m['inputs']), "",
                  "| 步骤 | 参数 | 数值 | 单位 | 依据类型 | 出处／假设 |", "| --- | --- | --- | --- | --- | --- |"]
        for i,s in enumerate(m['steps'],1):
            for p in s['parameters']:
                refs = "; ".join(f"{c['document']}:{c['locator']}" for c in p.get('evidence',[]))
                extra = p.get('reason') or p.get('rationale') or p.get('assumptions') or ''
                cells=[str(i)+'. '+s['action'],p['name'],str(p['value']) if p['value'] is not None else '未确定',p['unit'],p['origin'],refs+' '+extra]
                lines += ['| '+' | '.join(str(x).replace('|','/').replace('\n',' ') for x in cells)+' |']
        for key,label in [('checkpoints','过程检查'),('characterization','表征'),('gaps','缺口')]:
            lines += ['',f"**{label}**",'']+['- '+x for x in m[key]]
    lines += ['', '## 约束与未确定事项', '']
    lines += ['- '+c['id']+': '+c['status']+' — '+c['reason'] for c in data.get('constraint_assessments',[])]
    lines += ['- '+u['id']+': '+u['question']+' ['+u['importance']+']' for u in data.get('uncertainties',[])]
    for e in data.get('validation_experiments',[]):
        lines += ['',f"## 最小验证 {e['id']}",'',f"对应方法：{', '.join(e['method_ids'])}；不确定性：{', '.join(e['uncertainty_ids'])}。",'',
                  '**假设：** '+e['hypothesis'],'','**对照：** '+'; '.join(e['controls']),'',
                  f"独立合成批次：{e['independent_batches']}；每批技术重复：{e['technical_repeats']}。",e['sample_size_rationale'],'',
                  '**采样：** '+e['sampling'],'','| 指标 | 方法 | 单位 | 接受条件 | 条件依据 |','| --- | --- | --- | --- | --- |']
        lines += ['| '+' | '.join(r[k].replace('|','/') for k in ('metric','method','unit','acceptance','acceptance_basis'))+' |' for r in e['readouts']]
        lines += ['', '**预测：** '+e['predicted_result'],'','**可证伪条件：** '+e['falsification'],'','**结果分支：** '+e['decision_rule']]
    lines += ['', '## 来源', '']
    registry=read(Path(source)/'registry.json')
    lines += [f"- [{d['id']} — {d['title']}]({d['url']})；DOI: {d.get('doi','')}；范围: {d['access']}。" for d in registry['documents']]
    result=assess(Path(source),Path(artifact))
    lines += ['', '## 检查结果', '',f"文档检查通过：{result['valid']}；科学有效性：{result['scientific_validity']}。",'']
    lines += ['- '+x for x in result['errors']]
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text('\n'.join(lines)+'\n')
    return result


def compare(source, artifacts, out):
    results=[dict(label=label,artifact=str(path),assessment=assess(Path(source),Path(path))) for label,path in artifacts]
    report=dict(status='completed', comparisons=results, recommended=False,
                comparison_scope='document quality only; no experimental benefit or independent chemical adjudication',
                decision='Human scientific review and wet-lab validation required. Equal results permit KEEP_BASE.')
    dump(out,report)
    return report
