"""Presentation regressions, zero live model calls."""
from html.parser import HTMLParser
from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

PLUGIN=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PLUGIN/'src'),str(PLUGIN/'vendor')]
from biomethod.html_report import render_html, render_job_report, safe_url
from biomethod.reporting import render
from biomethod.cli import main


class Tags(HTMLParser):
    def __init__(self):super().__init__();self.tags=[];self.attrs=[]
    def handle_starttag(self,tag,attrs):self.tags.append(tag);self.attrs.append(dict(attrs))


class HTMLReportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=PLUGIN/'examples/gelma/task/source'
        self.artifact=PLUGIN/'examples/gelma/curated-method.json'
        self.data=json.loads(self.artifact.read_text());self.out=self.root/'report.html'
    def tearDown(self):self.temp.cleanup()
    def generate(self,**kw):render_html(self.source,self.artifact,self.out,**kw);return self.out.read_text()
    def test_offline_demo_cannot_claim_execution(self):
        s=self.generate();self.assertIn('未完成全流程核验',s);self.assertIn('draft_missing_evidence',s)
        self.assertIn('不证明合成效果',s);self.assertNotIn('核心执行证据已核验</span>',s)
    def test_no_active_source_content_or_url(self):
        data=copy.deepcopy(self.data);data['material']='<script>alert(1)</script>'
        artifact=self.root/'method.json';artifact.write_text(json.dumps(data))
        render_html(self.source,artifact,self.out);s=self.out.read_text();p=Tags();p.feed(s)
        self.assertNotIn('script',p.tags);self.assertIn('&lt;script&gt;',s)
        for url in ['javascript:alert(1)','data:text/html,hi','file:///etc/passwd','//evil.test','https://[broken']:
            self.assertIsNone(safe_url(url))
        self.assertEqual(safe_url('https://example.org/a?b=1&c=2'),'https://example.org/a?b=1&c=2')
    def test_no_external_resources_responsive_accessible_print(self):
        s=self.generate();p=Tags();p.feed(s)
        self.assertFalse(set(p.tags)&{'script','iframe','link','img','object','embed'})
        self.assertIn('@media print',s);self.assertIn('prefers-reduced-motion',s)
        self.assertIn('Content-Security-Policy',s)
        ids={a['id'] for a in p.attrs if 'id' in a}
        for a in p.attrs:
            if a.get('href','').startswith('#'):self.assertIn(a['href'][1:],ids)
        self.assertIn('viewport',s);self.assertIn('scope="col"',s)
    def test_all_experiments_and_parameter_origins_present(self):
        s=self.generate()
        from html import escape
        for m in self.data['candidate_methods']:
            self.assertIn(escape(m['id']),s)
            for step in m['steps']:
                for p in step['parameters']:
                    self.assertIn(escape(p['name']),s);self.assertIn(escape(p['origin']),s)
        for e in self.data['validation_experiments']:
            for key in ('hypothesis','falsification','decision_rule','sample_size_rationale'):
                self.assertIn(escape(e[key]),s)
        self.assertIn('未确定',s)
    def test_render_extension_dispatch_and_markdown_compatibility(self):
        self.assertTrue(render(self.source,self.artifact,self.out)['valid'])
        self.assertTrue(self.out.read_text().startswith('<!doctype html>'))
        md=self.root/'method.md';render(self.source,self.artifact,md)
        self.assertTrue(md.read_text().startswith('---'))
    def test_stage_differences_rules_and_3w(self):
        comparison=dict(stages=[dict(label='base1',executed=True,artifact=str(self.artifact),assessment=dict(valid=False),parameter_changes=[])],rule_edits=[dict(notes='KEEP_BASE')])
        s=self.generate(proof=dict(verified=True),comparison=comparison,literature=dict(literature_review=[dict(why='WHY-TOKEN',how='HOW-TOKEN',what='WHAT-TOKEN')]))
        for token in ['核心执行证据已核验','base1','KEEP_BASE','WHY-TOKEN','HOW-TOKEN','WHAT-TOKEN','该阶段实际方法']:
            self.assertIn(token,s)
    def test_saved_proof_is_rechecked_and_missing_artifact_fails(self):
        (self.root/'execution-evidence.json').write_text('{"verified":true}')
        with patch('biomethod.execution.execution_evidence',return_value={}) as check:
            with self.assertRaises(ValueError):render_job_report(self.root)
            check.assert_called_once()
    def test_curated_demo_exports_html_without_models(self):
        out=self.root/'demo'
        self.assertEqual(main(['demo','--out',str(out)]),0)
        self.assertTrue((out/'method.html').is_file());self.assertTrue((out/'method.md').is_file())
        self.assertIn('未完成全流程核验',(out/'method.html').read_text())

    def test_progressive_disclosure_and_branch_diagram(self):
        s=self.generate();parser=Tags();parser.feed(s)
        self.assertIn('svg',parser.tags)
        self.assertGreater(parser.tags.count('details'),10)
        self.assertFalse(any('open' in a for a in parser.attrs))
        for title in ['完整目标、约束、假设与证据边界','依据与计算','对照、采样、接受条件与结果分支','完整文档检查与错误记录']:
            self.assertIn(title,s)
        self.assertIn('Baseline分别进入INV和DOM',s)
        self.assertIn('独立批次 / 技术重复',s)
        self.assertIn('预期结果',s);self.assertIn('可证伪条件',s)
    def test_stage_and_final_method_anchors_are_unique(self):
        stage=dict(label='base1',executed=True,artifact=str(self.artifact),assessment=dict(valid=True),parameter_changes=[])
        s=self.generate(comparison=dict(stages=[stage,dict(stage,label='inv1')]))
        parser=Tags();parser.feed(s)
        ids=[a['id'] for a in parser.attrs if 'id' in a]
        self.assertEqual(len(ids),len(set(ids)))
        for a in parser.attrs:
            if a.get('href','').startswith('#'):self.assertIn(a['href'][1:],ids)
    def test_collapsed_support_preserves_source_and_experiment_values(self):
        s=self.generate()
        from html import escape
        for m in self.data['candidate_methods']:
            for step in m['steps']:
                for p in step['parameters']:
                    for ref in p.get('evidence',[]):
                        self.assertIn(escape(ref['quote']),s)
        for e in self.data['validation_experiments']:
            for r in e['readouts']:
                for key in ('metric','method','unit','acceptance','acceptance_basis'):
                    self.assertIn(escape(str(r[key])),s)
