"""Article-style, source-bound bilingual reports; no scripts or model calls."""
from __future__ import annotations
from html import escape
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import json
import re
from urllib.parse import urlsplit
from .workflow import read
from .validation import assess
from .report_language import report_payload,content_hash,required_strings,validate_localization


def esc(value):return escape(str(value),quote=True)


def safe_url(url):
    try:
        p=urlsplit(str(url));return str(url) if p.scheme.lower() in ('http','https') and p.netloc else None
    except ValueError:return None
CSS = '''
:root{--ink:#152e39;--muted:#53676e;--accent:#00685f;--paper:#fffdf8;--line:#d7ded9;--wash:#eef3ef;--warning:#7a4215}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.75 "Avenir Next","PingFang SC","Microsoft YaHei",sans-serif}a{color:var(--accent);text-underline-offset:4px}a:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:4px}.skip{position:absolute;top:-80px}.skip:focus{top:8px;background:white;z-index:5;padding:12px}.shell{max-width:1500px;margin:auto;display:grid;grid-template-columns:240px minmax(0,1fr)}nav{padding:40px 26px;position:sticky;top:0;height:100vh;border-right:1px solid var(--line)}.brand{font-weight:800;font-size:20px;letter-spacing:-.8px}.brand i{color:var(--accent);font-style:normal}nav small,.eyebrow{display:block;color:var(--accent);font-size:11px;letter-spacing:2px;text-transform:uppercase;font-weight:700}nav ol{list-style:none;padding:36px 0;margin:0}nav li{margin:16px 0}nav a{text-decoration:none;font-size:14px}nav .note{font-size:12px;color:var(--muted)}main{min-width:0;padding:48px 5vw 72px}header{padding-bottom:36px;border-bottom:2px solid var(--ink)}h1,h2{font-family:"Iowan Old Style","Songti SC",Georgia,serif;font-weight:500;letter-spacing:-1px}h1{font-size:clamp(38px,5vw,66px);line-height:1.15;margin:22px 0}h1 span{color:var(--accent)}.lead{font-size:19px;color:var(--muted);max-width:760px}.meta{font-size:13px;color:var(--muted)}section{padding:38px 0;border-bottom:1px solid var(--line)}h2{font-size:31px;line-height:1.4;margin:0 0 24px}h2 b{font:12px "Avenir Next",sans-serif;color:var(--accent);display:block;letter-spacing:2px;margin-bottom:8px}h3{font-size:19px;margin:24px 0 12px}h4{font-size:16px;margin:20px 0 8px}.notice{border-left:3px solid var(--warning);padding:16px 20px;background:#fbf0df;color:#653911;margin:24px 0}.stamp{display:inline-block;color:var(--accent);border:1px solid var(--accent);padding:3px 10px;font-size:12px}.stamp.warn{color:var(--warning);border-color:var(--warning)}.flow{display:flex;flex-wrap:wrap;gap:8px;margin:24px 0}.flow span{border-bottom:2px solid var(--accent);padding:8px 12px;font-size:13px}.fields{margin:0}.fields>div{display:grid;grid-template-columns:minmax(120px,23%) minmax(0,1fr);gap:18px;padding:10px 0;border-bottom:1px solid #e6e9e3}dt{font-size:13px;color:var(--muted)}dd{margin:0;min-width:0;overflow-wrap:anywhere}p{overflow-wrap:anywhere}ul{padding-left:21px}li{margin:7px 0}.table-wrap{overflow-x:auto;max-width:100%;margin:16px 0}table{border-collapse:collapse;width:100%;font-size:14px;min-width:580px;text-align:left}th{background:var(--wash);font-size:12px;color:var(--muted);font-weight:700}td,th{padding:12px;vertical-align:top;border-bottom:1px solid var(--line);overflow-wrap:anywhere}td .fields>div{display:block}td dt{font-size:11px}details{margin:12px 0;padding:10px 16px;background:var(--wash)}summary{cursor:pointer;font-size:14px;font-weight:600}article{margin:28px 0;padding-top:12px}article+article{border-top:1px solid var(--line)}.step{padding:14px 0}.step h4{color:var(--accent)}footer{padding-top:24px;font-size:12px;color:var(--muted)}code{font-size:12px;overflow-wrap:anywhere}pre{white-space:pre-wrap;font-size:12px;overflow-wrap:anywhere}::selection{background:#cee3d8}
@media(max-width:850px){.shell{display:block}nav{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line);padding:20px 24px}nav ol{display:flex;flex-wrap:wrap;gap:8px 18px;padding:12px 0 0}nav li{margin:0}nav small,nav .note{display:none}main{padding:30px 24px}.fields>div{grid-template-columns:1fr;gap:4px}h1{font-size:42px}h2{font-size:27px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{@page{margin:16mm}body{background:white;font-size:10pt;line-height:1.5}.shell{display:block}nav,.skip{display:none}main{padding:0}h1{font-size:32pt}h2{font-size:21pt}section{padding:20px 0}h2,h3,h4,summary{break-after:avoid}article,.step{break-inside:auto}.table-wrap{overflow:visible}table{min-width:0;font-size:8pt;table-layout:fixed}th{background:white}details{background:white}details::details-content{content-visibility:visible}details>*{display:block!important}summary{list-style:none}a{color:inherit}.notice{background:white}thead{display:table-header-group}tr{break-inside:avoid}}
'''
CSS += '\n/* Reading hierarchy v2: conclusions and comparison tables first, support folded. */\nmain{max-width:1220px;padding:36px 42px 64px}header{padding-bottom:22px}h1{font-size:38px;margin:14px 0;line-height:1.25}h1 br{display:none}h1 span{margin-left:14px;font-size:26px}.lead{font-size:16px;margin:10px 0}.notice{margin:16px 0;padding:12px 16px;font-size:13px}.section-intro{color:var(--muted);font-size:14px;margin:0 0 18px}.finding{border-left:3px solid var(--accent);padding:12px 18px;background:var(--wash);margin:20px 0}.finding p{margin:8px 0 0;font-size:15px}.jump-links{display:flex;flex-wrap:wrap;gap:12px 24px;margin:14px 0 24px}.jump-links a{font-size:13px;font-weight:600}details.support{background:transparent;padding:0;border:1px solid var(--line);border-radius:4px;margin:10px 0}details.support>summary{padding:11px 14px;color:var(--accent);font-size:13px;font-weight:600}details.support[open]>summary{border-bottom:1px solid var(--line);background:var(--wash)}.detail-body{padding:14px 16px;min-width:0}td details.support{border:0;margin:0;max-width:340px}td details.support>summary{padding:0;white-space:nowrap}td details.support[open]>summary{padding:6px 0;background:transparent}td .detail-body{padding:10px 0}.detail-body .fields>div{display:block}.detail-body dt{font-weight:600;margin-bottom:4px}.detail-body dd{font-size:13px}table{font-size:13px;min-width:560px}td,th{padding:10px 12px}th{white-space:nowrap}.harness-map{margin:10px 0 20px;overflow-x:auto}.harness-map svg{display:block;width:100%;min-width:540px;max-height:205px}.harness-map figcaption{font-size:12px;color:var(--muted);margin-top:8px}.route-flow{display:flex;flex-wrap:wrap;list-style:none;padding:0;gap:8px;margin:24px 0}.route-flow li{display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--wash);font-size:12px}.route-flow li:not(:last-child)::after{content:"→";margin-left:6px;color:var(--accent)}.route-flow span,.step-no{color:var(--accent);font-weight:700}.step h4{display:flex;gap:14px;color:var(--ink);font-size:14px;font-weight:500;line-height:1.7}.step-no{font-size:20px;flex:0 0 28px}.unknown{color:var(--warning)}h3 .meta{display:block;font-weight:400;margin-top:4px}section{padding:30px 0}h2{font-size:27px}article{margin:20px 0}details table{min-width:480px}.detail-body>ul{margin-top:0}.meta{overflow-wrap:anywhere}\n@media(max-width:850px){main{padding:24px 18px}h1{font-size:30px}h1 span{display:block;margin:6px 0 0;font-size:22px}h2{font-size:24px}nav{padding:16px 18px}.table-wrap{margin:12px 0}.detail-body{padding:10px}.step h4{font-size:13px}}\n@media print{main{max-width:none;padding:0}h1{font-size:24pt}h1 span{font-size:18pt}.jump-links{display:none}details.support>summary{color:var(--ink)}.harness-map svg{min-width:0}table,details table{min-width:0}.detail-body{padding:6px}td details.support{max-width:none}summary{white-space:normal!important}}\n'

CSS += '.decision-map{border-top:2px solid var(--accent);margin:22px 0}.decision-start{padding:14px;background:var(--wash);font-size:14px}.decision-branches{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.decision-branches p{font-size:12px;border-top:1px solid var(--line);padding-top:10px}.decision-branches b{display:block;font-size:14px;margin-bottom:8px}.decision-branches span{color:var(--muted)}@media(max-width:650px){.decision-branches{grid-template-columns:1fr;gap:0}}'


CSS += '''
.language-bar{display:flex;justify-content:space-between;align-items:center;padding:14px 30px;border-bottom:1px solid var(--line);background:var(--paper)}.language-options{display:flex;gap:6px}.language-options label{padding:5px 14px;border:1px solid var(--line);border-radius:3px;cursor:pointer;font-size:13px}.language-control{position:absolute;left:-10000px}#lang-zh:checked~.language-bar label[for="lang-zh"],#lang-en:checked~.language-bar label[for="lang-en"]{background:var(--accent);color:white}#lang-zh:focus-visible~.language-bar label[for="lang-zh"],#lang-en:focus-visible~.language-bar label[for="lang-en"]{outline:3px solid var(--warning);outline-offset:3px}#lang-zh:checked~.report-en,#lang-en:checked~.report-zh{display:none}.language-options label.unavailable{opacity:.5;cursor:not-allowed}h1{font-size:34px;margin:12px 0}.eyebrow{letter-spacing:1px}blockquote{border-left:2px solid var(--line);padding:5px 12px;margin:10px 0;font-size:13px;color:var(--muted)}.synthesis-flow{counter-reset:flow;list-style:none;padding:0;margin:20px 0}.synthesis-flow>li{position:relative;display:grid;grid-template-columns:36px minmax(0,1fr);gap:14px;padding:0 0 20px}.synthesis-flow>li:not(:last-child)::before{content:"";position:absolute;left:17px;top:32px;bottom:0;border-left:2px solid var(--line)}.flow-index{position:relative;z-index:1;border:1px solid var(--accent);border-radius:50%;background:var(--paper);color:var(--accent);width:36px;height:36px;text-align:center;line-height:34px;font-size:12px}.flow-step{padding:12px 16px;background:var(--wash);border-radius:4px}.flow-step h4{margin:0 0 6px;font-size:16px}.flow-step p{font-size:13px;margin:6px 0}.gate-note{border-left:2px solid var(--warning);padding-left:10px;color:var(--warning);font-size:12px}.experiment-roadmap{border-top:2px solid var(--accent);padding-top:12px;margin:22px 0}.experiment-roadmap ol{padding-left:22px}.experiment-roadmap li{margin:10px 0}.badge{display:inline-block;padding:2px 8px;border:1px solid var(--line);font-size:11px}.reference-assessment{margin:18px 0}.source-principle{font-size:13px;color:var(--muted)}.run-note{font-size:12px;color:var(--muted)}.report .meta{max-width:100%}@media print{.language-bar{display:none}.report-en,.report-zh{display:block}#lang-zh:checked~.report-en,#lang-en:checked~.report-zh{display:none}.synthesis-flow>li{break-inside:avoid}}@media(max-width:650px){.language-bar{padding:12px 18px}.brand{font-size:17px}h1{font-size:29px}.flow-step{padding:10px 12px}}
'''

CSS += '.synthesis-flow>li:not(:last-child)::after{content:"";position:absolute;left:13px;bottom:2px;border:5px solid transparent;border-top-color:var(--accent)}'

FIELDS={
 'target':('目标','Target'),'scale':('规模与基准','Scale and basis'),'application':('用途','Application'),'constraints':('约束','Constraints'),
 'schema_version':('数据格式版本','Schema version'),'material':('材料','Material'),'metric':('指标','Metric'),'value':('数值','Value'),
 'unit':('单位','Unit'),'tolerance':('允许偏差','Tolerance'),'definition':('定义','Definition'),'assay':('测定方式','Assay'),'basis':('基准','Basis'),
 'available_equipment':('可用设备','Available equipment'),'unknown_fields':('未确定条件','Unknown fields'),'assumption_notes':('场景假设','Scenario assumptions'),
 'id':('编号','ID'),'kind':('类型','Type'),'description':('说明','Description'),'status':('状态','Status'),'reason':('判断依据','Rationale'),
 'inputs':('原料与设备','Inputs and equipment'),'checkpoints':('过程检查','Checkpoints'),'characterization':('表征','Characterization'),'gaps':('方法缺口','Method gaps'),
 'evidence_limitations':('证据边界','Evidence limitations'),'origin':('依据类型','Origin'),'expression':('计算表达式','Expression'),
 'evidence':('证据','Evidence'),'document':('来源编号','Document'),'locator':('定位','Locator'),'quote':('原文引句','Original quotation'),
 'assumptions':('假设','Assumptions'),'rationale':('依据','Rationale'),'uncertainty':('对应未知事项','Uncertainty'),'uncertainty_ids':('对应未知事项','Uncertainty IDs'),
 'calculation':('计算','Calculation'),'source':('来源','Source'),'note':('说明','Note'),'notes':('说明','Notes'),'limitations':('局限','Limitations'),
 'method_ids':('对应方法','Method IDs'),'hypothesis':('待检验假设','Hypothesis'),'controls':('对照','Controls'),'sampling':('采样','Sampling'),
 'independent_batches':('独立合成批次','Independent synthesis batches'),'technical_repeats':('每批技术重复','Technical repeats per batch'),
 'sample_size_rationale':('批次与重复数依据','Batch and repeat rationale'),'predicted_result':('预期结果','Expected result'),
 'falsification':('可证伪条件','Falsification'),'decision_rule':('结果分支','Decision rule'),'acceptance':('接受条件','Acceptance'),
 'acceptance_basis':('条件依据','Basis for acceptance'),'readouts':('读出','Readouts'),'method':('检测方法','Measurement method'),
 'target_assessment':('目标判断','Target assessment'),'constraint_assessments':('约束核对','Constraint assessments'),'uncertainties':('未确定事项','Uncertainties'),
 'importance':('重要性','Importance'),'question':('问题','Question'),'valid':('文档检查通过','Document checks passed'),'score':('文档检查分数','Document score'),
 'scientific_validity':('科学有效性','Scientific validity'),'errors':('检查错误','Check errors'),'warnings':('检查边界','Check limitations'),
 'critical':('关键错误','Critical errors'),'adoptable':('可直接采用','Adoptable'),'route_id':('来源路线','Source route'),'disposition':('处置','Disposition'),
 'why':('为什么相关','Why relevant'),'how':('采用什么方法','How conducted'),'what':('结果与边界','Findings and limits'),'method_evidence':('方法证据','Method evidence'),
 'source_gaps':('未取得的来源','Missing source material'),'title':('标题','Title'),'url':('链接','URL'),'doi':('DOI','DOI'),
 'access':('访问范围','Access'),'path':('本地路径','Local path'),'sha256':('校验值','SHA-256'),'license':('许可','License'),
}


class Article:
    def __init__(self,language,pack=None):
        self.language=language;self.pack=pack or {};self.strings={'full_text':'全文','fulltext':'全文','curated_excerpt':'已登记摘录',**self.pack.get('zh',{})};self.prefix=language+'-'
    def L(self,zh,en):return zh if self.language=='zh' else en
    def text(self,value,key=''):
        text=str(value)
        if key not in ('quote','title','url','doi','path','sha256'):
            mapping=self.strings if self.language=='zh' else self.pack.get('en',{})
            text=mapping.get(text,text)
        return esc(text).replace('\n','<br>')
    def value(self,value,key=''):
        if value is None:return '<strong class="unknown">'+self.L('未确定','Unknown')+'</strong>'
        if isinstance(value,bool):return self.L('是','Yes') if value else self.L('否','No')
        if isinstance(value,dict):
            return '<dl class="fields">'+''.join('<div><dt>'+esc(self.L(*FIELDS[k]) if k in FIELDS else k.replace('_',' '))+'</dt><dd>'+self.value(v,k)+'</dd></div>' for k,v in value.items())+'</dl>'
        if isinstance(value,list):return '<ul>'+''.join('<li>'+self.value(v,key)+'</li>' for v in value)+'</ul>' if value else '<span class="meta">'+self.L('无记录','Not recorded')+'</span>'
        if key=='quote':return '<blockquote lang="en">'+self.text(value,key)+'</blockquote>'
        return self.text(value,key)
    def table(self,headers,rows):
        return '<div class="table-wrap" tabindex="0" role="region" aria-label="'+self.L('数据表，可横向滚动','Data table; scroll horizontally if needed')+'"><table><thead><tr>'+''.join('<th scope="col">'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+c+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    def fold(self,title,body):return '<details class="support"><summary>'+esc(title)+'</summary><div class="detail-body">'+body+'</div></details>'
    def link(self,anchor,label):return '<a href="#'+self.prefix+anchor+'">'+esc(label)+'</a>'
    def flow(self,method,namespace):
        presentation=self.pack.get('method_flow',{}).get(method.get('id'),[])
        steps=method.get('steps',[]);items=[]
        for i,step in enumerate(steps):
            note=presentation[i] if len(presentation)==len(steps) else {}
            label=note.get(self.language,{}).get('label') or self.L('步骤 '+str(i+1),'Step '+str(i+1))
            # Conditions come directly from the original parameters; never retype numeric values.
            params=step.get('parameters',[])
            known=[p for p in params if p.get('value') is not None and len(str(p['value']))<90 and 'sum(' not in str(p['value'])]
            selected=known[:2]
            conditions='; '.join(self.text(p.get('name'))+' = '+self.value(p.get('value'))+' '+self.text(p.get('unit','')) for p in selected)
            unknown=sum(p.get('value') is None for p in params)
            gate=self.L('仍有 '+str(unknown)+' 项参数未确定；见下方步骤表。',str(unknown)+' parameters remain unknown; see step table below.') if unknown else self.L('具体执行条件见步骤表；文献值不等于已验证结果。','See the step table for execution conditions; reported values are not verified outcomes.')
            desc=note.get(self.language,{}).get('purpose')
            if not desc:desc=self.strings.get(step.get('action',''),step.get('action','')) if self.language=='zh' else step.get('action','')
            anchor=self.prefix+namespace+'-step-'+str(i+1)
            items.append('<li><span class="flow-index">'+str(i+1).zfill(2)+'</span><div class="flow-step"><h4><a href="#'+anchor+'">'+esc(label)+'</a></h4><p>'+esc(desc)+'</p><p>'+conditions+'</p><div class="gate-note">'+gate+'</div></div></li>')
        return '<ol class="synthesis-flow" aria-label="'+self.L('合成方法逻辑流程图','Synthesis method logic flowchart')+'">'+''.join(items)+'</ol>'
    def method(self,method,namespace='final',flow=True):
        namespace=namespace+'-'+hashlib.sha256(str(method.get('id','')).encode()).hexdigest()[:8]
        body='<article class="method"><h3>'+self.text(method.get('id',''))+'</h3>'
        if flow:body+=self.flow(method,namespace)
        body+=self.fold(self.L('原料、设备、过程检查与表征','Inputs, equipment, checkpoints and characterization'),self.value({k:v for k,v in method.items() if k!='steps'}))
        for i,step in enumerate(method.get('steps',[]),1):
            body+='<div class="step" id="'+self.prefix+namespace+'-step-'+str(i)+'"><h4><span class="step-no">'+str(i).zfill(2)+'</span>'+self.text(step.get('action',''))+'</h4>'
            rows=[]
            for param in step.get('parameters',[]):
                extra={k:v for k,v in param.items() if k not in ('name','value','unit','origin')}
                rows.append([self.text(param.get('name','')),self.value(param.get('value'))+' <span class="meta">'+self.text(param.get('unit',''))+'</span>',self.text(param.get('origin','')),self.fold(self.L('依据与计算','Evidence and calculation'),self.value(extra))])
            body+=self.table([self.L('参数','Parameter'),self.L('数值 / 单位','Value / unit'),self.L('依据类型','Origin'),self.L('支撑材料','Supporting material')],rows)+'</div>'
        return body+'</article>'
    def trace(self,proof,comparison):
        # Node geometry is an explanatory logical diagram, not wall-clock scheduling evidence.
        labels=[('Baseline',self.L('原始方法','Original method')),('INV',self.L('通用执行与检查','General execution')),('DOM',self.L('材料与科学约束','Domain reasoning')),('AGG',self.L('合成修改决定','Aggregate rule edits'))]
        marker=self.prefix+'trace-arrow'
        boxes=[(5,65,160,70,self.L('基线','Baseline'),self.L('原始方法','Original method')),(270,13,170,70,'INV',self.L('通用执行与检查','General execution')),(270,117,170,70,'DOM',self.L('材料与科学约束','Domain reasoning')),(550,65,150,70,'AGG',self.L('合成修改决定','Aggregate edits')),(755,65,140,70,self.L('选择交付','Selection'),self.L('反思与保存','Reflect and save'))]
        body='<figure class="harness-map"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 200" role="img" aria-label="'+self.L('Baseline分别进入INV和DOM，两路修改合成AGG','Baseline branches to INV and DOM; both feed AGG')+'"><defs><marker id="'+marker+'" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#00685f"/></marker></defs><g fill="none" stroke="#00685f" stroke-width="2" marker-end="url(#'+marker+')"><path d="M165 100H210V48H270"/><path d="M210 100V152H270"/><path d="M440 48H490V100H550"/><path d="M440 152H490V100"/><path d="M700 100H755"/></g>'
        for x,y,w,h,title,subtitle in boxes:
            body+='<rect x="'+str(x)+'" y="'+str(y)+'" width="'+str(w)+'" height="'+str(h)+'" rx="6" fill="#eef3ef" stroke="#bdcec5"/><text x="'+str(x+w/2)+'" y="'+str(y+29)+'" text-anchor="middle" fill="#152e39" font-size="17">'+esc(title)+'</text><text x="'+str(x+w/2)+'" y="'+str(y+54)+'" text-anchor="middle" fill="#53676e" font-size="12">'+esc(subtitle)+'</text>'
        body+='</svg></figure>'
        rows=[]
        for stage in comparison.get('stages',[]):
            valid=stage.get('assessment',{}).get('valid')
            rows.append([esc(stage.get('label','')),self.value(stage.get('executed')),self.value(valid),str(len(stage.get('parameter_changes',[])))])
        body+=self.table([self.L('阶段','Stage'),self.L('实际执行','Executed'),self.L('文档检查通过','Document check passed'),self.L('参数变化数','Parameter changes')],rows)
        body+='<p class="meta">'+self.L('参数未改变不代表阶段未运行。阶段检查与实验有效性是不同判断。','Unchanged parameters do not mean a stage was skipped. Document checks do not establish experimental validity.')+'</p>'
        for edit in comparison.get('rule_edits',proof.get('rule_edits',[])):
            label=edit.get('label','')
            note=self.pack.get('rule_summaries',{}).get(label,{})
            content=note.get(self.language) if note else None
            if content is None:content=edit.get('notes','') if self.language=='en' else self.L('原始规则记录保留在英文视图及执行报告中。','')
            body+=self.fold(label+' · '+self.L('规则修改','Rule changes'),'<p>'+esc(content)+'</p>')
        # Full stage artifacts remain in the English archival view; never pretend they were translated.
        if self.language=='en':
            for stage in comparison.get('stages',[]):
                path=Path(stage['artifact']) if stage.get('artifact') else None
                if path and path.is_file():
                    try:
                        data=read(path);details=self.value(stage.get('assessment',{}))+self.value(stage.get('parameter_changes',[]))
                        details+=self.fold('Actual stage method',''.join(self.method(m,stage.get('label','stage'),False) for m in data.get('candidate_methods',[])))
                        details+=self.fold('Stage experiments and other fields',self.value({k:v for k,v in data.items() if k!='candidate_methods'}))
                        body+=self.fold(stage.get('label','')+' · original stage archive',details)
                    except (ValueError,OSError,TypeError,AttributeError) as exc:body+='<p>'+esc(exc)+'</p>'
        else:
            body+='<p class="run-note">完整阶段方法为英文原始归档，可在英文视图查看；中文视图保留执行与变化摘要。</p>'
        summary={k:proof.get(k) for k in ('selected','reflection_executed','delivery_repair_executed','model_sessions_attempted','model_sessions_verified')}
        if self.language=='en':body+=self.fold('Selection and execution receipts',self.value(proof))
        else:body+=self.table(['记录','结果'],[['最终交付',esc(str(summary['selected']))],['反思已执行',self.value(summary['reflection_executed'])],['另行交付修复',self.value(summary['delivery_repair_executed'])],['记录的模型会话数',self.value(summary['model_sessions_attempted'])]])
        return body


def _article(language,pack,goal,data,literature,registry,proof,comparison,usage,assessment,references,artifact_hash):
    R=Article(language,pack);L=R.L;v=R.value;sections=[]
    def add(anchor,title,body):
        sections.append((anchor,title,'<section id="'+R.prefix+anchor+'"><h2><b>'+str(len(sections)+1).zfill(2)+'</b>'+esc(title)+'</h2>'+body+'</section>'))
    target=goal.get('target',{});scale=goal.get('scale',{})
    brief=R.table([L('目标','Target'),L('允许偏差','Tolerance'),L('规模','Scale'),L('检测方式','Assay')],[[v(target.get('value'))+' '+R.text(target.get('unit','')),v(target.get('tolerance')),v(scale.get('value'))+' '+R.text(scale.get('unit','')),v(target.get('assay'))]])
    brief+='<div class="finding"><span class="eyebrow">'+L('当前判断','Current assessment')+'</span><p>'+v(data.get('target_assessment',{}).get('reason'))+'</p></div>'
    brief+=R.fold(L('完整目标、约束、假设与证据边界','Full aim, constraints, assumptions and evidence limits'),v(goal)+v(data.get('evidence_limitations',[])))
    add('brief',L('目标与边界','Aim and boundaries'),brief)
    lit=''
    overview=pack.get('material_overview',{}).get(language)
    if overview:lit+='<p>'+esc(overview)+'</p>'
    for entry in literature.get('literature_review',[]):
        lit+='<article><h3>'+R.text(entry.get('document',''))+'</h3>'+R.table([L('问题','Question'),L('文献理解','Literature understanding')],[[L(zh,en),v(entry.get(key))] for key,zh,en in [('why','为什么相关','Why relevant'),('how','采用什么方法','How conducted'),('what','结果与适用边界','Findings and applicability')]])
        lit+=R.fold(L('原文引句与定位（保留原文）','Original quotations and locators'),v(entry.get('method_evidence',[])))+'</article>'
    if not lit:lit='<p>'+L('没有提供文献提取记录；不补写综述结论。','No literature extraction supplied; no review conclusions are invented.')+'</p>'
    lit+=R.fold(L('缺失来源与补充材料','Missing sources and supplements'),v(literature.get('source_gaps',[])))
    add('literature',L('文献理解','Literature understanding'),lit)
    methods='<p>'+L('以下是待验证的候选方法。流程图说明步骤之间的顺序及准入条件；不是已执行的实验结果。','The following methods are candidates for validation. The flowchart shows sequence and readiness gates, not completed laboratory results.')+'</p>'
    methods+=''.join(R.method(m) for m in data.get('candidate_methods',[]))
    methods+='<div id="'+R.prefix+'process">'+R.fold(L('候选方法如何形成：Baseline / INV / DOM / AGG','How the candidate was developed: Baseline / INV / DOM / AGG'),R.trace(proof,comparison))+'</div>'
    add('methods',L('候选合成方法','Candidate synthesis method'),methods)
    unknowns=R.table([L('未知事项','Open question'),L('重要性','Importance'),L('需要回答的问题','Question to resolve')],[[esc(u.get('id','')),v(u.get('importance')),v(u.get('question'))] for u in data.get('uncertainties',[])])
    unknowns+=R.fold(L('目标约束核对','Constraint assessments'),R.table([L('约束','Constraint'),L('状态','Status'),L('判断依据','Rationale')],[[esc(c.get('id','')),v(c.get('status')),v(c.get('reason'))] for c in data.get('constraint_assessments',[])]))
    add('unknowns',L('尚未确定什么','What remains unresolved'),unknowns)
    experiments=''
    roadmap=pack.get('experiment_roadmap',[])
    if roadmap:
        experiments+='<div class="experiment-roadmap"><ol>'
        for entry in roadmap:
            item=entry.get(language,{})
            experiments+='<li><b>'+esc(entry.get('id',''))+' · '+esc(item.get('label',''))+'</b></li>'
        experiments+='</ol><p class="gate-note">'+L('此顺序来自当前实验设计；后续阶段须满足各自前置条件。','This sequence comes from the present experimental design; later stages retain their stated prerequisites.')+'</p></div>'
    rows=[]
    for e in data.get('validation_experiments',[]):
        summary=next((x.get(language,{}) for x in roadmap if x.get('id')==e.get('id')), {})
        rows.append([esc(e.get('id','')),esc(summary['label']) if summary.get('label') else v(e.get('hypothesis')),v([r.get('metric','') for r in e.get('readouts',[])]),esc(summary['resolves']) if summary.get('resolves') else v(e.get('uncertainty_ids',[])),v(e.get('independent_batches'))+' / '+v(e.get('technical_repeats'))])
    experiments+=R.table([L('实验','Experiment'),L('验证什么','What it tests'),L('检测什么','What to measure'),L('完成后能明确什么','What it can resolve'),L('计划批次 / 技术重复','Planned batches / technical repeats')],rows)
    experiments+='<p class="meta">'+L('这些是计划值，并非已完成实验。技术重复不等于独立合成批次；实验阈值须按各自的依据解释。','These are planned counts, not completed experiments. Technical repeats are not independent synthesis batches; interpret thresholds according to their stated basis.')+'</p>'
    for e in data.get('validation_experiments',[]):
        body='<h4>'+L('待检验假设与设计','Hypothesis and design')+'</h4>'+v({k:e.get(k) for k in ('hypothesis','method_ids','uncertainty_ids','controls','sampling','sample_size_rationale')})
        body+='<h4>'+L('检测与接受条件','Readouts and acceptance conditions')+'</h4>'+R.table([L('指标','Metric'),L('检测方式 / 单位','Method / unit'),L('接受条件','Acceptance'),L('条件依据','Basis')],[[v(r.get('metric')),v(r.get('method'))+' / '+v(r.get('unit')),v(r.get('acceptance')),v(r.get('acceptance_basis'))] for r in e.get('readouts',[])])
        body+=R.table([L('判断','Decision'),L('内容','Content')],[[L(zh,en),v(e.get(k))] for k,zh,en in [('predicted_result','预期结果','Expected result'),('falsification','可证伪条件','Falsification'),('decision_rule','通过／失败／无法判断时的行动','Pass / fail / inconclusive actions')]])
        experiments+=R.fold(e.get('id','')+' · '+L('对照、采样、接受条件与结果分支','Controls, sampling, acceptance and decisions'),body)
    add('experiments',L('最小验证实验','Minimal validation experiments'),experiments)
    profiles={r.get('id'):r for r in references.get('documents',[])};refs=''
    for doc in registry.get('documents',[]):
        meta=profiles.get(doc['id'],{});url=safe_url(doc.get('url',''));title=esc(doc.get('title',''))
        refs+='<article class="reference-assessment"><h3>'+esc(doc['id'])+' · '+(('<a href="'+esc(url)+'">'+title+'</a>') if url else title)+'</h3>'
        bibliography=R.table([L('期刊','Journal'),L('年份','Year'),L('引用次数','Citation count'),L('数据来源 / 获取时间','Provider / retrieved at')],[[esc(meta.get('journal') or L('未获取','Not retrieved')),esc(meta.get('year') or L('未获取','Not retrieved')),v(meta.get('citation_count')),esc(meta.get('provider','Europe PMC'))+' / '+esc(meta.get('retrieved_at') or L('未获取','Not retrieved'))]])
        refs+=bibliography
        assessment_rows=[(L('全文可追溯性','Full-text traceability'),L('已登记全文，可核对原文引句；不等同于科学结论已复核。','Full text is registered and quotations can be checked; this does not certify scientific conclusions.')) if doc.get('access') in ('full_text','fulltext','fulltext_unreviewed') else (L('来源访问范围','Source access'),R.strings.get(str(doc.get('access')),str(doc.get('access'))) if language=='zh' else str(doc.get('access')))]
        for row in pack.get('reference_assessments',{}).get(doc['id'],[]):
            entry=row.get(language,{})
            assessment_rows.append((entry.get('dimension',''),entry.get('finding','')))
        assessment_rows.append((L('独立复现','Independent replication'),L('尚未核验引用论文是否实际复现本方法，不能据引用数判为高可信。','Citing papers have not been checked for actual replication; citation counts do not establish high method confidence.')))
        assessment_rows.append((L('对本任务目标的支持','Support for this task target'),L('详见第一部分的目标判断；文献影响力不能替代目标相关的直接证据。','See the task assessment in Aim; scholarly influence cannot replace target-specific direct evidence.')))
        refs+=R.table([L('证据维度','Evidence dimension'),L('评价与边界','Assessment and limits')],[[esc(a),esc(b)] for a,b in assessment_rows])
        metadata_url=safe_url(meta.get('query_url',''))
        refs+=R.fold(L('文献元数据、查询依据与文档检查','Bibliographic metadata, lookup provenance and document checks'),v({k:doc.get(k) for k in ('doi','access')})+('<p>'+L('许可标记：','License: ')+esc((re.search(r'CC BY(?:-[A-Z]+)* [0-9.]+',str(doc.get('license',''))) or (['CC BY 4.0'] if 'creativecommons.org/licenses/by/4.0' in str(doc.get('license','')) else ['未明确']))[0])+'</p>' if language=='zh' else v({'license':doc.get('license')}))+('<p><a href="'+esc(metadata_url)+'">'+L('查看引用量查询来源','View citation-count lookup')+'</a></p>' if metadata_url else '')+('<p>'+esc(meta.get('error',''))+'</p>' if language=='en' else '')+('<p>'+L('文档检查通过。其检查的是结构、算术和引用，不证明实验有效。','Document checks passed; they check structure, arithmetic and provenance, not experimental validity.')+'</p>' if assessment.get('valid') else '<p>'+L('文档检查未通过。','Document checks failed.')+'</p>')+(R.fold('Full machine check',v(assessment)) if language=='en' else ''))
        refs+='</article>'
    refs+='<p class="source-principle">'+L('引用次数反映传播与使用背景，不等于独立复现次数。期刊或影响因子不能替代对方法本身、适用条件和实验结果的审查。','Citation counts indicate scholarly attention, not independent replications. Journal metrics cannot replace assessment of a method, its conditions and experimental results.')+' <a href="https://sfdora.org/read/">'+L('评价原则参考','Assessment principles')+' · DORA</a></p>'
    add('sources',L('参考文献与证据评价','References and evidence assessment'),refs)
    nav=''.join('<li>'+R.link(a,str(i).zfill(2)+' / '+title)+'</li>' for i,(a,title,_) in enumerate(sections,1))
    state=L('核心执行证据已核验','Core execution evidence verified') if proof.get('verified') is True else L('未完成全流程核验 / 仅文档呈现','Full workflow unverified / document presentation only')
    material=esc(data.get('material','Biomaterial'))
    heading=material+L(' 合成方法',' synthesis method')
    boundary=L('候选方法尚未经过本任务的湿实验验证；不证明目标达成、纯度、生物相容性、实验安全性或可重复性。','This candidate has not undergone wet-lab validation in this task. It does not establish target attainment, purity, biocompatibility, operational safety or reproducibility.')
    footer=L('方法文件校验值','Method artifact SHA-256')+': <code>'+artifact_hash+'</code>'
    return '<div class="report report-'+language+'" lang="'+('zh-CN' if language=='zh' else 'en')+'"><a class="skip" href="#'+R.prefix+'main">'+L('跳到正文','Skip to report')+'</a><div class="shell"><nav aria-label="'+L('报告目录','Report contents')+'"><ol>'+nav+'</ol><p class="note">'+L('支撑材料按需展开。<br>单文件，支持离线阅读。','Expand supporting material as needed.<br>Single file; readable offline.')+'</p></nav><main id="'+R.prefix+'main"><header><h1>'+heading+'</h1><p class="meta">'+L('方法状态：','Method status: ')+R.text(data.get('status',''))+'</p><span class="stamp'+('' if proof.get('verified') else ' warn')+'">'+state+'</span><div class="notice">'+boundary+'</div></header>'+''.join(s[2] for s in sections)+'<footer>'+footer+'</footer></main></div></div>'


def render_html(source,artifact,out,*,proof=None,comparison=None,literature=None,usage=None,localization=None,references=None):
    source=Path(source);out=Path(out);data=read(artifact);goal=read(source/'goal.json');registry=read(source/'registry.json')
    assessment=assess(source,Path(artifact));literature=literature or {};proof=proof or {};comparison=comparison or {};references=references or {}
    pack=localization or {};translated=False
    if localization is not None:
        validate_localization(pack,report_payload(goal,data,literature));translated=True
    if pack.get('rule_summaries'):
        rule_hash=hashlib.sha256(json.dumps(comparison.get('rule_edits',proof.get('rule_edits',[])),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if pack.get('rule_hash')!=rule_hash:raise ValueError('Translated rule summaries do not match execution records.')
    en=_article('en',pack,goal,data,literature,registry,proof,comparison,usage,assessment,references,hashlib.sha256(Path(artifact).read_bytes()).hexdigest())
    zh=_article('zh',pack,goal,data,literature,registry,proof,comparison,usage,assessment,references,hashlib.sha256(Path(artifact).read_bytes()).hexdigest()) if translated else ''
    # Native radio controls keep the report offline and script-free. Each panel declares its own lang.
    source_is_english=not any(re.search(r'[\u3400-\u9fff]',text) for text in required_strings(report_payload(goal,data,literature)))
    controls='<input class="language-control" type="radio" id="lang-zh" name="report-language"'+(' checked' if translated else ' disabled')+'><input class="language-control" type="radio" id="lang-en" name="report-language"'+('' if translated else ' checked')+'><div class="language-bar"><span class="brand">RobinBioMethod</span><div class="language-options" role="group" aria-label="Language / 语言"><label for="lang-zh"'+('' if translated else ' class="unavailable" title="Chinese translation has not been prepared"')+'>中文</label><label for="lang-en">'+('English' if translated or source_is_english else 'Source / 原文')+'</label></div></div>'
    pending='' if translated else '<p class="notice">'+('Chinese translation is not prepared. This is the English report; translated headings alone are not presented as a Chinese edition.' if source_is_english else 'Language editions are not prepared. This is an untranslated source view, not a fully English or Chinese edition.')+'</p>'
    html='<!doctype html><html lang="'+('zh-CN' if translated else 'en')+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;"><title>'+esc(data.get('material','Biomaterial'))+' · RobinBioMethod</title><style>'+CSS+'</style></head><body>'+controls+pending+zh+en+'</body></html>'
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(html,encoding='utf-8')
    return dict(assessment,report_languages=['zh','en'] if translated else ['source'],localization_complete=translated)


def _saved(job,proof=None):
    job=Path(job);run=job/'harness' if (job/'harness').is_dir() else job
    if proof is None:
        from .execution import execution_evidence
        proof=execution_evidence(run,job/'budget.json' if (job/'budget.json').exists() else None,job/'audit' if (job/'audit').exists() else None)
    artifact=proof.get('delivery_artifact')
    if not artifact or not Path(artifact).is_file():raise ValueError('No readable delivery artifact; HTML cannot substitute a missing method.')
    return job,run,proof,Path(artifact)


def export_report_texts(job,out):
    job,run,proof,artifact=_saved(job)
    literature=read(job/'extraction.json') if (job/'extraction.json').exists() else {}
    payload=report_payload(read(run/'frozen/source/goal.json'),read(artifact),literature)
    from robinharness.runtime import dump
    result=dict(schema_version=1,source_hash=content_hash(payload),zh={text:None for text in required_strings(payload)},en={text:None for text in required_strings(payload) if re.search(r'[\u3400-\u9fff]',text)})
    dump(Path(out),result);return dict(status='translation_template_exported',out=str(out),strings=len(result['zh']),model_calls=0)


def render_job_report(job,proof=None,localization=None):
    job,run,proof,artifact=_saved(job,proof)
    comparison=read(run/'stage-comparison.json') if (run/'stage-comparison.json').exists() else {}
    literature=read(job/'extraction.json') if (job/'extraction.json').exists() else {}
    language_path=Path(localization) if localization else job/'report-localization.json'
    pack=read(language_path) if language_path.exists() else None
    refs=read(job/'reference-profile.json') if (job/'reference-profile.json').exists() else {}
    result=render_html(run/'frozen/source',artifact,job/'report.html',proof=proof,comparison=comparison,literature=literature,localization=pack,references=refs)
    from robinharness.runtime import dump
    dump(job/'report-presentation.json',dict(languages=result['report_languages'],localization_complete=result['localization_complete'],method_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),reference_metadata_cached=bool(refs),model_calls=0))
    return job/'report.html'
