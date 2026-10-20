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


def method_html(method):
    text='<article><h3>'+esc(method.get('id','方法'))+' · '+esc(method.get('route_id',''))+'</h3>'
    text+=value_html({k:v for k,v in method.items() if k!='steps'})
    for i,step in enumerate(method.get('steps',[]),1):
        text+='<div class="step"><h4>'+str(i).zfill(2)+' / '+esc(step.get('action','步骤'))+'</h4>'
        rows=[]
        for p in step.get('parameters',[]):
            rows.append([esc(p.get('name','')),value_html(p.get('value')),esc(p.get('unit','')),esc(p.get('origin','')),
                         value_html({k:v for k,v in p.items() if k not in ('name','value','unit','origin')})])
        text+=table(['参数','数值','单位','依据类型','出处／假设／计算'],rows)
        text+=value_html({k:v for k,v in step.items() if k not in ('action','parameters')})+'</div>'
    return text+'</article>'


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
    section('brief','01 / DESIGN BRIEF','目标与证据边界',value_html(goal)+value_html(data.get('target_assessment',{}))+value_html(data.get('evidence_limitations',[]))+value_html({k:v for k,v in data.items() if k not in ('candidate_methods','target_assessment','evidence_limitations','validation_experiments','constraint_assessments','uncertainties')}))
    lit=literature.get('literature_review',[])
    section('literature','02 / LITERATURE','文献理解 · 3W',value_html(lit)+value_html({'source_gaps':literature.get('source_gaps',[])}) if lit else '<p class="meta">本次渲染未提供 3W 提取记录；不补写文献结论。请核对来源与原始提取文件。</p>')
    stages=comparison.get('stages',[])
    stage_text='<div class="flow">'+''.join('<span>'+s+'</span>' for s in ['Baseline →','INV →','DOM →','AGG →','Selection / Reflection'])+'</div><p>这是执行顺序示意；实际执行与文档检查分别见下表。保留原方案也是合法结果，阶段一致不证明实验有效。</p>'
    stage_text+=table(['阶段','实际执行','文档检查','相对基线参数变化'],[[esc(s.get('label','')),value_html(s.get('executed')),value_html(s.get('assessment',{}).get('valid')),str(len(s.get('parameter_changes',[])))] for s in stages]) if stages else '<p class="meta">没有提供阶段执行记录。</p>'
    for s in stages:
        stage_text+='<details><summary>'+esc(s.get('label',''))+' · 参数变化与检查</summary>'+value_html({k:v for k,v in s.items() if k not in ('artifact','rendered')})
        # Include actual stage content, not just filenames, for a portable single file.
        path=Path(s['artifact']) if s.get('artifact') else None
        if path and path.is_file():
            try:
                stage_text+='<h3>该阶段实际方法</h3>'+''.join(method_html(m) for m in read(path).get('candidate_methods',[]))
            except (OSError,ValueError,TypeError,AttributeError) as exc:
                stage_text+='<p>阶段方法无法读取：'+esc(exc)+'</p>'
        else:stage_text+='<p>本次渲染无法读取该阶段原始方法文件。</p>'
        stage_text+='</details>'
    stage_text+='<h3>规则修改与合成决定</h3>'+value_html(comparison.get('rule_edits',proof.get('rule_edits',[])))
    stage_text+='<h3>选择、反思与执行用量</h3>'+value_html({k:proof.get(k) for k in ('selected','selector','reflection_executed','experience_saved','delivery_repair_executed','model_sessions_attempted','model_sessions_verified')})
    stage_text+=value_html(usage or {'usage':'本次渲染未提供预算记录；未调用模型。'})
    section('process','03 / HARNESS² TRACE','Baseline / INV / DOM / AGG',stage_text)
    section('methods','04 / CANDIDATE METHODS','候选合成方法',''.join(method_html(m) for m in data.get('candidate_methods',[])))
    experiments=''
    for e in data.get('validation_experiments',[]):
        experiments+='<article><h3>'+esc(e.get('id','实验'))+' / 最小验证实验</h3>'+value_html(e)+'</article>'
    section('experiments','05 / DISCRIMINATING EXPERIMENTS','最小验证实验',experiments)
    section('unknowns','06 / OPEN QUESTIONS','约束与未确定事项',value_html(data.get('constraint_assessments',[]))+value_html(data.get('uncertainties',[])))
    sources=''
    for d in registry.get('documents',[]):
        url=safe_url(d.get('url',''));title=esc(d.get('id','')+' · '+d.get('title',''))
        sources+='<article><h3>'+(('<a href="'+esc(url)+'" rel="noreferrer">'+title+'</a>') if url else title)+'</h3>'+value_html({k:v for k,v in d.items() if k not in ('title','url')})+'</article>'
    section('sources','07 / PROVENANCE','来源与检查',sources+'<h3>文档检查结果</h3>'+value_html(result))
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
