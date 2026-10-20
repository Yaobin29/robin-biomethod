"""Offline editorial reports, rendered from structured artifacts without model calls.

Design adapts local frontend-design typography/composition and frontend-skill
navigation principles. No global skill, JavaScript, font service or CDN is required.
All source strings are untrusted; never interpolate them as markup or active URLs.
"""
from __future__ import annotations
from html import escape
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from urllib.parse import urlsplit
from .workflow import read
from .validation import assess

CSS = '''
:root{--ink:#152e39;--muted:#53676e;--accent:#00685f;--paper:#fffdf8;--line:#d7ded9;--wash:#eef3ef;--warning:#7a4215}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.75 "Avenir Next","PingFang SC","Microsoft YaHei",sans-serif}a{color:var(--accent);text-underline-offset:4px}a:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:4px}.skip{position:absolute;top:-80px}.skip:focus{top:8px;background:white;z-index:5;padding:12px}.shell{max-width:1500px;margin:auto;display:grid;grid-template-columns:240px minmax(0,1fr)}nav{padding:40px 26px;position:sticky;top:0;height:100vh;border-right:1px solid var(--line)}.brand{font-weight:800;font-size:20px;letter-spacing:-.8px}.brand i{color:var(--accent);font-style:normal}nav small,.eyebrow{display:block;color:var(--accent);font-size:11px;letter-spacing:2px;text-transform:uppercase;font-weight:700}nav ol{list-style:none;padding:36px 0;margin:0}nav li{margin:16px 0}nav a{text-decoration:none;font-size:14px}nav .note{font-size:12px;color:var(--muted)}main{min-width:0;padding:48px 5vw 72px}header{padding-bottom:36px;border-bottom:2px solid var(--ink)}h1,h2{font-family:"Iowan Old Style","Songti SC",Georgia,serif;font-weight:500;letter-spacing:-1px}h1{font-size:clamp(38px,5vw,66px);line-height:1.15;margin:22px 0}h1 span{color:var(--accent)}.lead{font-size:19px;color:var(--muted);max-width:760px}.meta{font-size:13px;color:var(--muted)}section{padding:38px 0;border-bottom:1px solid var(--line)}h2{font-size:31px;line-height:1.4;margin:0 0 24px}h2 b{font:12px "Avenir Next",sans-serif;color:var(--accent);display:block;letter-spacing:2px;margin-bottom:8px}h3{font-size:19px;margin:24px 0 12px}h4{font-size:16px;margin:20px 0 8px}.notice{border-left:3px solid var(--warning);padding:16px 20px;background:#fbf0df;color:#653911;margin:24px 0}.stamp{display:inline-block;color:var(--accent);border:1px solid var(--accent);padding:3px 10px;font-size:12px}.stamp.warn{color:var(--warning);border-color:var(--warning)}.flow{display:flex;flex-wrap:wrap;gap:8px;margin:24px 0}.flow span{border-bottom:2px solid var(--accent);padding:8px 12px;font-size:13px}.fields{margin:0}.fields>div{display:grid;grid-template-columns:minmax(120px,23%) minmax(0,1fr);gap:18px;padding:10px 0;border-bottom:1px solid #e6e9e3}dt{font-size:13px;color:var(--muted)}dd{margin:0;min-width:0;overflow-wrap:anywhere}p{overflow-wrap:anywhere}ul{padding-left:21px}li{margin:7px 0}.table-wrap{overflow-x:auto;max-width:100%;margin:16px 0}table{border-collapse:collapse;width:100%;font-size:14px;min-width:580px;text-align:left}th{background:var(--wash);font-size:12px;color:var(--muted);font-weight:700}td,th{padding:12px;vertical-align:top;border-bottom:1px solid var(--line);overflow-wrap:anywhere}td .fields>div{display:block}td dt{font-size:11px}details{margin:12px 0;padding:10px 16px;background:var(--wash)}summary{cursor:pointer;font-size:14px;font-weight:600}article{margin:28px 0;padding-top:12px}article+article{border-top:1px solid var(--line)}.step{padding:14px 0}.step h4{color:var(--accent)}footer{padding-top:24px;font-size:12px;color:var(--muted)}code{font-size:12px;overflow-wrap:anywhere}pre{white-space:pre-wrap;font-size:12px;overflow-wrap:anywhere}::selection{background:#cee3d8}
@media(max-width:850px){.shell{display:block}nav{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line);padding:20px 24px}nav ol{display:flex;flex-wrap:wrap;gap:8px 18px;padding:12px 0 0}nav li{margin:0}nav small,nav .note{display:none}main{padding:30px 24px}.fields>div{grid-template-columns:1fr;gap:4px}h1{font-size:42px}h2{font-size:27px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{@page{margin:16mm}body{background:white;font-size:10pt;line-height:1.5}.shell{display:block}nav,.skip{display:none}main{padding:0}h1{font-size:32pt}h2{font-size:21pt}section{padding:20px 0}h2,h3,h4,summary{break-after:avoid}article,.step{break-inside:auto}.table-wrap{overflow:visible}table{min-width:0;font-size:8pt;table-layout:fixed}th{background:white}details{background:white}details::details-content{content-visibility:visible}details>*{display:block!important}summary{list-style:none}a{color:inherit}.notice{background:white}thead{display:table-header-group}tr{break-inside:avoid}}
'''
CSS += '\n/* Reading hierarchy v2: conclusions and comparison tables first, support folded. */\nmain{max-width:1220px;padding:36px 42px 64px}header{padding-bottom:22px}h1{font-size:38px;margin:14px 0;line-height:1.25}h1 br{display:none}h1 span{margin-left:14px;font-size:26px}.lead{font-size:16px;margin:10px 0}.notice{margin:16px 0;padding:12px 16px;font-size:13px}.section-intro{color:var(--muted);font-size:14px;margin:0 0 18px}.finding{border-left:3px solid var(--accent);padding:12px 18px;background:var(--wash);margin:20px 0}.finding p{margin:8px 0 0;font-size:15px}.jump-links{display:flex;flex-wrap:wrap;gap:12px 24px;margin:14px 0 24px}.jump-links a{font-size:13px;font-weight:600}details.support{background:transparent;padding:0;border:1px solid var(--line);border-radius:4px;margin:10px 0}details.support>summary{padding:11px 14px;color:var(--accent);font-size:13px;font-weight:600}details.support[open]>summary{border-bottom:1px solid var(--line);background:var(--wash)}.detail-body{padding:14px 16px;min-width:0}td details.support{border:0;margin:0;max-width:340px}td details.support>summary{padding:0;white-space:nowrap}td details.support[open]>summary{padding:6px 0;background:transparent}td .detail-body{padding:10px 0}.detail-body .fields>div{display:block}.detail-body dt{font-weight:600;margin-bottom:4px}.detail-body dd{font-size:13px}table{font-size:13px;min-width:560px}td,th{padding:10px 12px}th{white-space:nowrap}.harness-map{margin:10px 0 20px;overflow-x:auto}.harness-map svg{display:block;width:100%;min-width:540px;max-height:205px}.harness-map figcaption{font-size:12px;color:var(--muted);margin-top:8px}.route-flow{display:flex;flex-wrap:wrap;list-style:none;padding:0;gap:8px;margin:24px 0}.route-flow li{display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--wash);font-size:12px}.route-flow li:not(:last-child)::after{content:"→";margin-left:6px;color:var(--accent)}.route-flow span,.step-no{color:var(--accent);font-weight:700}.step h4{display:flex;gap:14px;color:var(--ink);font-size:14px;font-weight:500;line-height:1.7}.step-no{font-size:20px;flex:0 0 28px}.unknown{color:var(--warning)}h3 .meta{display:block;font-weight:400;margin-top:4px}section{padding:30px 0}h2{font-size:27px}article{margin:20px 0}details table{min-width:480px}.detail-body>ul{margin-top:0}.meta{overflow-wrap:anywhere}\n@media(max-width:850px){main{padding:24px 18px}h1{font-size:30px}h1 span{display:block;margin:6px 0 0;font-size:22px}h2{font-size:24px}nav{padding:16px 18px}.table-wrap{margin:12px 0}.detail-body{padding:10px}.step h4{font-size:13px}}\n@media print{main{max-width:none;padding:0}h1{font-size:24pt}h1 span{font-size:18pt}.jump-links{display:none}details.support>summary{color:var(--ink)}.harness-map svg{min-width:0}table,details table{min-width:0}.detail-body{padding:6px}td details.support{max-width:none}summary{white-space:normal!important}}\n'

CSS += '.decision-map{border-top:2px solid var(--accent);margin:22px 0}.decision-start{padding:14px;background:var(--wash);font-size:14px}.decision-branches{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.decision-branches p{font-size:12px;border-top:1px solid var(--line);padding-top:10px}.decision-branches b{display:block;font-size:14px;margin-bottom:8px}.decision-branches span{color:var(--muted)}@media(max-width:650px){.decision-branches{grid-template-columns:1fr;gap:0}}'

LABELS = dict(target='目标', scale='规模与基准', raw_material='起始材料', equipment='设备', unknown_fields='未确定条件',
              application='应用', metric='指标', value='数值', unit='单位', tolerance='允许偏差', definition='定义', assay='测定方法',
              basis='基准', status='状态', reason='判断依据', inputs='原料与设备', checkpoints='过程检查', characterization='表征', gaps='证据缺口',
              hypothesis='待检验假设', controls='对照', independent_batches='独立合成批次', technical_repeats='每批技术重复',
              sample_size_rationale='样本数依据', sampling='采样', readouts='读出与接受条件', predicted_result='预测结果',
              falsification='可证伪条件', decision_rule='通过／失败／不确定时的行动', method_ids='对应方法', uncertainty_ids='对应未知事项',
              document='来源编号', locator='定位', quote='原文引句', origin='依据类型', evidence='原文证据', assumptions='假设',
              expression='计算表达式', name='名称', acceptance='接受条件', acceptance_basis='条件依据', method='测定方法',
              why='Why · 研究意义', how='How · 方法', what='What · 结果与边界', method_evidence='方法证据',
              source_gaps='未获得的来源', importance='重要性', question='问题', disposition='处置', route_id='来源路线',
              errors='检查错误', warnings='检查边界', valid='文档检查通过', scientific_validity='科学有效性', score='文档检查分数')


def esc(value):
    return escape(str(value), quote=True)


def value_html(value):
    """Lossless field rendering; null is always visibly unknown, never blank."""
    if value is None:
        return '<strong class="unknown">未确定</strong>'
    if isinstance(value, bool):
        return '是' if value else '否'
    if isinstance(value, dict):
        return '<dl class="fields">'+''.join('<div><dt>'+esc(LABELS.get(k,k))+'</dt><dd>'+value_html(v)+'</dd></div>' for k,v in value.items())+'</dl>'
    if isinstance(value, list):
        return '<ul>'+''.join('<li>'+value_html(v)+'</li>' for v in value)+'</ul>' if value else '<span class="meta">无记录</span>'
    return esc(value).replace('\n','<br>')


def table(head, rows):
    return '<div class="table-wrap" tabindex="0" role="region" aria-label="数据表，可横向滚动"><table><thead><tr>'+''.join('<th scope="col">'+esc(h)+'</th>' for h in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+c+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def fold(title, body):
    return '<details class="support"><summary>'+esc(title)+'</summary><div class="detail-body">'+body+'</div></details>'


def compact(value):
    return value_html(value)


def method_html(method, namespace="final"):
    method_key=namespace+str(method.get("id",""))
    text='<article class="method"><h3>'+esc(method.get('id','方法'))+' <span class="meta">'+esc(method.get('route_id',''))+'</span></h3>'
    steps=method.get('steps',[])
    text+='<p class="meta">'+str(len(steps))+' 个步骤 · 参数在正文中查看；出处与计算按需展开。</p>'
    text+=fold('原料、设备、过程检查与方法缺口',value_html({k:v for k,v in method.items() if k!='steps'}))
    text+='<ol class="route-flow" aria-label="合成步骤概览">'+''.join('<li><span>'+str(i).zfill(2)+'</span><a href="#method-'+hashlib.sha256(method_key.encode()).hexdigest()[:8]+'-'+str(i)+'">步骤 '+str(i)+' · '+str(len(step.get('parameters',[])))+' 项参数</a></li>' for i,step in enumerate(steps,1))+'</ol>'
    for i,step in enumerate(steps,1):
        anchor='method-'+hashlib.sha256(method_key.encode()).hexdigest()[:8]+'-'+str(i)
        text+='<div class="step" id="'+anchor+'"><h4><span class="step-no">'+str(i).zfill(2)+'</span>'+esc(step.get('action','步骤'))+'</h4>'
        rows=[]
        for param in step.get('parameters',[]):
            origin=param.get('origin','')
            origin_label={'reported':'文献报告','calculated':'计算值','proposed':'提出值','unknown':'未确定','assumed':'假设'}.get(origin,origin)
            support={k:v for k,v in param.items() if k not in ('name','value','unit','origin')}
            rows.append([esc(param.get('name','')),value_html(param.get('value'))+' <span class="meta">'+esc(param.get('unit',''))+'</span>',
                         '<span title="'+esc(origin)+'">'+esc(origin_label)+'</span>',fold('依据与计算',value_html(support)) if support else '<span class="meta">无记录</span>'])
        text+=table(['参数','数值 / 单位','依据类型','支撑材料'],rows)
        extra={k:v for k,v in step.items() if k not in ('action','parameters')}
        if extra:text+=fold('步骤补充说明',value_html(extra))
        text+='</div>'
    return text+'</article>'


def harness_diagram():
    # This is a conceptual branch/merge map, not an assertion of wall-clock parallelism.
    return '''<figure class="harness-map"><svg viewBox="0 0 900 200" role="img" aria-label="Baseline分别进入INV和DOM，两路修改合成AGG，再选择交付；示意逻辑关系，不代表并行执行时间。" xmlns="http://www.w3.org/2000/svg"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#00685f"/></marker></defs><g fill="none" stroke="#00685f" stroke-width="2" marker-end="url(#arrow)"><path d="M165 100H210V48H270"/><path d="M210 100V152H270"/><path d="M440 48H490V100H550"/><path d="M440 152H490V100"/><path d="M700 100H755"/></g><g fill="#f0f5f1" stroke="#bdcec5"><rect x="5" y="65" width="160" height="70" rx="6"/><rect x="270" y="13" width="170" height="70" rx="6"/><rect x="270" y="117" width="170" height="70" rx="6"/><rect x="550" y="65" width="150" height="70" rx="6"/><rect x="755" y="65" width="140" height="70" rx="6"/></g><g fill="#152e39" text-anchor="middle" font-family="sans-serif" font-size="17"><text x="85" y="94">Baseline</text><text x="85" y="119" font-size="12">原始方法</text><text x="355" y="43">INV</text><text x="355" y="67" font-size="12">通用执行与检查</text><text x="355" y="147">DOM</text><text x="355" y="171" font-size="12">材料与科学约束</text><text x="625" y="94">AGG</text><text x="625" y="119" font-size="12">合成修改决定</text><text x="825" y="94">选择交付</text><text x="825" y="119" font-size="12">反思与保存</text></g></svg><figcaption>逻辑关系示意：两类修改在 AGG 汇合；实际执行及检查结果见下表。</figcaption></figure>'''


def safe_url(url):
    """Allow only browser HTTP(S) navigation; reject data/javascript/file schemes."""
    try:
        parsed=urlsplit(str(url))
        return str(url) if parsed.scheme.lower() in ('http','https') and parsed.netloc else None
    except ValueError:
        return None


def render_html(source, artifact, out, *, proof=None, comparison=None, literature=None, usage=None):
    source=Path(source);out=Path(out)
    data=read(artifact);goal=read(source/'goal.json');registry=read(source/'registry.json')
    result=assess(source,Path(artifact))
    proof=proof or {};comparison=comparison or {};literature=literature or {}
    # Presentation cannot certify a workflow: only an explicit verified execution proof
    # distinguishes it from a standalone render/curated demo.
    verified=proof.get('verified') is True
    state='核心执行证据已核验' if verified else '未完成全流程核验 / 仅文档呈现'
    sections=[]
    def section(anchor,number,title,body):
        sections.append((anchor,title,'<section id="'+anchor+'"><h2><b>'+number+'</b>'+title+'</h2>'+body+'</section>'))
    target=goal.get('target',{});scale=goal.get('scale',{})
    summary=table(['目标值','允许偏差','规模','测定方式'],[[compact(target.get('value'))+' '+esc(target.get('unit','')),compact(target.get('tolerance')),compact(scale.get('value'))+' '+esc(scale.get('unit','')),compact(target.get('assay'))]])
    summary+='<div class="finding"><span class="eyebrow">当前判断 · '+esc(data.get('target_assessment',{}).get('status','未确定'))+'</span><p>'+compact(data.get('target_assessment',{}).get('reason','未提供目标判断。'))+'</p></div>'
    summary+='<p class="meta">阅读路径：先看当前判断 → 候选方法 → 最小实验；文献与过程用于追溯。</p><div class="jump-links"><a href="#methods">查看候选方法 ↓</a><a href="#experiments">查看最小实验 ↓</a><a href="#unknowns">查看未确定事项 ↓</a></div>'
    summary+=fold('完整目标、约束、假设与证据边界',value_html(goal)+value_html(data.get('evidence_limitations',[]))+value_html({k:v for k,v in data.items() if k not in ('candidate_methods','target_assessment','evidence_limitations','validation_experiments','constraint_assessments','uncertainties')}))
    section('brief','01 / DESIGN BRIEF','目标与证据边界',summary)
    lit=literature.get('literature_review',[])
    lit_text='<p class="section-intro">先看每篇文献回答了什么；方法原文与定位信息折叠保留。</p>'
    for entry in lit:
        lit_text+='<article><h3>'+esc(entry.get('document','文献'))+'</h3>'+table(['问题','文献提取结果'],[[esc(label),compact(entry.get(key))] for key,label in [('why','为什么相关'),('how','采用什么方法'),('what','结果与适用边界')]])
        lit_text+=fold('展开原文证据与定位',value_html({k:v for k,v in entry.items() if k not in ('document','why','how','what')}))+'</article>'
    if not lit:lit_text+='<p class="meta">本次渲染未提供 3W 提取记录；不补写文献结论。</p>'
    lit_text+=fold('缺失全文／补充材料记录',value_html(literature.get('source_gaps',[])))
    section('literature','02 / LITERATURE','文献理解 · 3W',lit_text)
    stages=comparison.get('stages',[])
    stage_text=harness_diagram()
    stage_text+=table(['阶段','实际执行','文档检查','相对基线参数变化'],[[esc(stage.get('label','')),value_html(stage.get('executed')),value_html(stage.get('assessment',{}).get('valid')),str(len(stage.get('parameter_changes',[])))] for stage in stages]) if stages else '<p class="meta">没有提供阶段执行记录。</p>'
    stage_text+='<p class="meta">变化数仅统计参数差异。规则、实验或说明可有修改；参数未改变不等于阶段未运行。</p>'
    stage_details=''
    for stage in stages:
        changes=stage.get('parameter_changes',[])
        body=table(['参数','基线','该阶段'],[[esc(c.get('parameter','')),compact(c.get('baseline')),compact(c.get('candidate'))] for c in changes]) if changes else '<p>参数值未检测到变化。请结合规则和实验记录判断。</p>'
        body+=fold('文档检查的具体结果',value_html(stage.get('assessment',{})))
        path=Path(stage['artifact']) if stage.get('artifact') else None
        if path and path.is_file():
            try:
                stage_data=read(path)
                body+=fold('该阶段实际方法', ''.join(method_html(m,stage.get("label","stage")) for m in stage_data.get('candidate_methods',[])))
                body+=fold('该阶段完整实验与其他字段',value_html({k:v for k,v in stage_data.items() if k!='candidate_methods'}))
            except (OSError,ValueError,TypeError,AttributeError) as exc:body+='<p>阶段方法无法读取：'+esc(exc)+'</p>'
        else:body+='<p>本次渲染无法读取该阶段原始方法文件。</p>'
        stage_details+=fold(stage.get('label','阶段')+' · 参数变化与检查',body)
    stage_text+=fold('逐阶段方法、差异和检查详情',stage_details)
    edits=comparison.get('rule_edits',proof.get('rule_edits',[]))
    stage_text+='<h3>规则修改与合成决定</h3>'+table(['阶段 / 维度','已执行','保留原规则','修改依据'],[[esc(e.get('label',''))+' / '+esc(e.get('dimension','')),compact(e.get('executed')),compact(e.get('kept_base')),fold('展开规则修改原文',compact(e.get('notes')))] for e in edits])
    stage_text+=fold('选择、反思与执行用量',value_html({k:proof.get(k) for k in ('selected','selector','reflection_executed','experience_saved','delivery_repair_executed','model_sessions_attempted','model_sessions_verified')})+value_html(usage or {'usage':'本次渲染未提供预算记录；未调用模型。'}))
    section('process','03 / HARNESS² TRACE','Baseline / INV / DOM / AGG',stage_text)
    section('methods','04 / CANDIDATE METHODS','候选合成方法','<p class="section-intro">按步骤查看参数。未确定值保持突出；引文、假设和计算藏在对应参数的“依据与计算”中。</p>'+''.join(method_html(m) for m in data.get('candidate_methods',[])))
    exps=data.get('validation_experiments',[])
    experiments=table(['实验','检验的假设','独立批次 / 技术重复','读出指标'],[[esc(e.get('id','')),compact(e.get('hypothesis')),compact(e.get('independent_batches'))+' / '+compact(e.get('technical_repeats')),compact([r.get('metric','') for r in e.get('readouts',[])])] for e in exps])
    experiments+='<div class="decision-map" role="group" aria-label="验证判断流程"><div class="decision-start">提出假设 → 设置对照与采样 → 测量读出 → 按预先约定的条件判断</div><div class="decision-branches"><p><b>符合接受条件</b><span>按该实验的结果分支决定下一步；不能直接宣称方法有效。</span></p><p><b>触发可证伪条件</b><span>按该实验记录，停止、修正或排除相关假设。</span></p><p><b>证据不足／无法区分</b><span>保留未确定状态，检查测定与缺失条件。</span></p></div></div>'
    experiments+='<p class="meta">批次与技术重复不能互换。下表的试验安排与接受条件是待验证设计，不是已得到的结果。实验间的先后依赖以各自条件为准。</p>'
    for e in exps:
        body='<h4>如何做</h4>'+table(['设计项目','内容'],[[esc(label),compact(e.get(key))] for key,label in [('method_ids','对应方法'),('uncertainty_ids','对应未知事项'),('controls','对照'),('sampling','采样'),('sample_size_rationale','批次与重复数依据')]])
        body+='<h4>看什么、怎样判断</h4>'+table(['指标','方法 / 单位','接受条件','条件依据'],[[compact(r.get('metric')),compact(r.get('method'))+' / '+compact(r.get('unit')),compact(r.get('acceptance')),compact(r.get('acceptance_basis'))] for r in e.get('readouts',[])])
        body+=table(['结果判断','行动依据'],[[esc(label),compact(e.get(key))] for key,label in [('predicted_result','预期结果'),('falsification','可证伪条件'),('decision_rule','通过／失败／不确定时的行动')]])
        extra={k:v for k,v in e.items() if k not in ('id','method_ids','uncertainty_ids','controls','sampling','sample_size_rationale','readouts','predicted_result','falsification','decision_rule','hypothesis','independent_batches','technical_repeats')}
        if extra:body+=fold('补充字段',value_html(extra))
        experiments+=fold(e.get('id','实验')+' · 对照、采样、接受条件与结果分支',body)
    section('experiments','05 / DISCRIMINATING EXPERIMENTS','最小验证实验',experiments)
    constraints=table(['约束','状态','原因'],[[esc(c.get('id','')),compact(c.get('status')),compact(c.get('reason'))] for c in data.get('constraint_assessments',[])])
    unknowns=table(['未知事项','重要性','需要回答的问题'],[[esc(u.get('id','')),compact(u.get('importance')),compact(u.get('question'))] for u in data.get('uncertainties',[])])
    section('unknowns','06 / OPEN QUESTIONS','约束与未确定事项','<h3>哪些条件尚未满足</h3>'+constraints+'<h3>哪些问题需要实验回答</h3>'+unknowns)
    sources=table(['来源','访问范围','详细记录'],[[('<a href="'+esc(safe_url(d.get('url','')))+'" rel="noreferrer">'+esc(d.get('id','')+' · '+d.get('title',''))+'</a>') if safe_url(d.get('url','')) else esc(d.get('id','')+' · '+d.get('title','')),compact(d.get('access')),fold('DOI、来源与登记信息',value_html({k:v for k,v in d.items() if k not in ('title','url')}))] for d in registry.get('documents',[])])
    sources+='<p>文档检查：<strong>'+('通过' if result['valid'] else '未通过')+'</strong>。科学有效性：'+esc(result.get('scientific_validity','未实验验证'))+'。</p>'+fold('完整文档检查与错误记录',value_html(result))
    section('sources','07 / PROVENANCE','来源与检查',sources)
    snapshot=esc(datetime.now(timezone.utc).isoformat(timespec='seconds'))
    digest=hashlib.sha256(Path(artifact).read_bytes()).hexdigest()
    title=esc(data.get('material','Biomaterial'))
    nav=''.join('<li><a href="#'+anchor+'">'+str(i).zfill(2)+' / '+label+'</a></li>' for i,(anchor,label,_) in enumerate(sections,1))
    document='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;"><title>'+title+' · RobinBioMethod</title><style>'+CSS+'</style></head><body><a class="skip" href="#main">跳到报告正文</a><div class="shell"><nav aria-label="报告目录"><div class="brand">Robin<i>BioMethod</i></div><small>Research method dossier</small><ol>'+nav+'</ol><p class="note">单文件 · 离线阅读<br>浏览器打印可保存为 PDF<br>无需联网、脚本或额外技能</p></nav><main id="main"><header><span class="eyebrow">LITERATURE → METHOD → VALIDATION PLAN</span><h1>'+title+'<br><span>从证据到候选方法</span></h1><p class="lead">候选合成方法、最小验证实验与可追溯的推理过程。</p><span class="stamp'+('' if verified else ' warn')+'">'+state+'</span><p class="meta">方法状态：'+esc(data.get('status','未确定'))+' · 文档检查：'+('通过' if result['valid'] else '未通过')+'</p><div class="notice"><strong>研究边界</strong><br>计算流程与文档检查不证明合成效果、目标达成、纯度、生物相容性、实验安全性或可重复性。未知条件和提出的实验阈值需要人工审阅与实验确认。</div></header>'+''.join(s[2] for s in sections)+'<footer>RobinBioMethod · Evidence-grounded method design<br>生成时间（UTC）：'+snapshot+'<br>方法快照 SHA-256：<code>'+digest+'</code><br>本页面由结构化结果确定性生成；原始 JSON、Markdown 与执行审计保留。HTML 排版不增加模型调用。</footer></main></div></body></html>'
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(document,encoding='utf-8')
    return result


def render_job_report(job, proof=None):
    """Render saved outputs only; never start/retry/charge a model session."""
    job=Path(job)
    run=job/'harness' if (job/'harness').is_dir() else job
    source=run/'frozen/source'
    if proof is None:
        from .execution import execution_evidence
        proof=execution_evidence(run,job/'budget.json' if (job/'budget.json').exists() else None,job/'audit' if (job/'audit').exists() else None)
    artifact=proof.get('delivery_artifact')
    if not artifact or not Path(artifact).is_file():
        raise ValueError('No readable delivery artifact; HTML rendering cannot substitute a missing method.')
    comparison=read(run/'stage-comparison.json') if (run/'stage-comparison.json').exists() else {}
    extraction=read(job/'extraction.json') if (job/'extraction.json').exists() else {}
    budget=read(job/'budget.json') if (job/'budget.json').exists() else {}
    sessions=budget.get('sessions',[])
    usage=dict(scope='This job budget only; previous attempts and separately authorized checks are not silently combined.',recorded_sessions=len(sessions),max_sessions=budget.get('max_sessions'),cost_usd=None,
               tokens={key:sum(s.get('usage',{}).get(key,0) for s in sessions) for key in ('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens')}) if budget else None
    render_html(source,Path(artifact),job/'report.html',proof=proof,comparison=comparison,literature=extraction,usage=usage)
    return job/'report.html'
