"""Presentation and translation contracts. Synthetic strings are not linguistic validation."""
from html.parser import HTMLParser
from pathlib import Path
import copy
import json
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

PLUGIN=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PLUGIN/'src'),str(PLUGIN/'vendor')]
from biomethod.html_report import render_html, render_job_report, safe_url
from biomethod.report_language import report_payload,content_hash,required_strings,numbers,validate_localization
from biomethod.reporting import render
from biomethod.cli import main


class Tags(HTMLParser):
    def __init__(self):super().__init__();self.tags=[];self.attrs=[];self.panel=None;self.depth=0;self.text={'zh':[],'en':[]};self.headings=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);self.tags.append(tag);self.attrs.append(a)
        if tag=='div' and ('report-zh' in a.get('class','').split() or 'report-en' in a.get('class','').split()):
            self.panel='zh' if 'report-zh' in a['class'] else 'en';self.depth=1
        elif self.panel and tag=='div':self.depth+=1
    def handle_endtag(self,tag):
        if self.panel and tag=='div':
            self.depth-=1
            if self.depth==0:self.panel=None
    def handle_data(self,data):
        if self.panel:self.text[self.panel].append(data)


class HTMLReportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=PLUGIN/'examples/gelma/task/source';self.artifact=PLUGIN/'examples/gelma/curated-method.json'
        self.data=json.loads(self.artifact.read_text());self.goal=json.loads((self.source/'goal.json').read_text());self.out=self.root/'report.html'
    def tearDown(self):self.temp.cleanup()
    def pack(self,literature=None):
        payload=report_payload(self.goal,self.data,literature or {})
        # Deliberately artificial translations test field routing and number guards, not science.
        return dict(schema_version=1,source_hash=content_hash(payload),zh={s:('测试译文 '+ ' '.join(numbers(s).elements())) if s else '' for s in required_strings(payload)})
    def generate(self,**kw):render_html(self.source,self.artifact,self.out,**kw);return self.out.read_text()
    def test_offline_demo_cannot_claim_execution(self):
        s=self.generate();self.assertIn('Full workflow unverified',s);self.assertIn('draft_missing_evidence',s)
        self.assertNotIn('Core execution evidence verified</span>',s)
    def test_missing_translation_disables_chinese_not_mixed_headings(self):
        s=self.generate();p=Tags();p.feed(s)
        self.assertFalse(p.text['zh']);self.assertTrue(p.text['en'])
        self.assertFalse(re.search('[\u3400-\u9fff]',''.join(p.text['en'])))
        self.assertIn('Chinese translation is not prepared',s)
        self.assertTrue(any(a.get('id')=='lang-zh' and 'disabled' in a for a in p.attrs))
    def test_complete_bilingual_panels_and_native_language_controls(self):
        s=self.generate(localization=self.pack());p=Tags();p.feed(s)
        self.assertTrue(p.text['zh']);self.assertTrue(p.text['en'])
        self.assertFalse(re.search('[\u3400-\u9fff]',''.join(p.text['en'])))
        self.assertNotIn(self.data['target_assessment']['reason'],''.join(p.text['zh']))
        self.assertIn('#lang-zh:checked~.report-en',s)
        self.assertTrue(any(a.get('id')=='lang-zh' and 'checked' in a for a in p.attrs))
        self.assertIn('lang="zh-CN"',s);self.assertIn('lang="en"',s)
    def test_stale_missing_numeric_and_english_passthrough_translations_rejected(self):
        payload=report_payload(self.goal,self.data,{})
        for kind in ('stale','missing','numeric','passthrough','prefix'):
            pack=self.pack();source=next(s for s in pack['zh'] if len(s)>60 and not numbers(s))
            if kind=='stale':pack['source_hash']='bad'
            if kind=='missing':del pack['zh'][source]
            if kind=='numeric':pack['zh'][source]='测试译文 999'
            if kind=='passthrough':pack['zh'][source]=source
            if kind=='prefix':pack['zh'][source]='中文：'+source
            with self.subTest(kind=kind),self.assertRaises(ValueError):validate_localization(pack,payload)
    def test_chinese_source_requires_real_english_translation(self):
        payload=dict(goal=dict(application='目标为80个基团'),data={},literature={})
        pack=dict(source_hash=content_hash(payload),zh={'目标为80个基团':'目标为80个基团'})
        with self.assertRaises(ValueError):validate_localization(pack,payload)
        pack['en']={'目标为80个基团':'Target is 80 groups'}
        validate_localization(pack,payload)
    def test_no_active_source_content_or_url(self):
        data=copy.deepcopy(self.data);data['material']='<script>alert(1)</script>'
        artifact=self.root/'method.json';artifact.write_text(json.dumps(data))
        render_html(self.source,artifact,self.out);s=self.out.read_text();p=Tags();p.feed(s)
        self.assertNotIn('script',p.tags);self.assertIn('&lt;script&gt;',s)
        for url in ['javascript:alert(1)','data:text/html,hi','file:///etc/passwd','//evil.test','https://[broken']:
            self.assertIsNone(safe_url(url))
    def test_offline_accessible_unique_language_stage_anchors(self):
        stage=dict(label='base1',executed=True,artifact=str(self.artifact),assessment=dict(valid=True),parameter_changes=[])
        s=self.generate(localization=self.pack(),comparison=dict(stages=[stage,dict(stage,label='inv1')]))
        p=Tags();p.feed(s);self.assertFalse(set(p.tags)&{'script','iframe','link','img','object','embed'})
        for token in ['@media print','prefers-reduced-motion','Content-Security-Policy','scope="col"']:self.assertIn(token,s)
        ids=[a['id'] for a in p.attrs if 'id' in a];self.assertEqual(len(ids),len(set(ids)))
        for a in p.attrs:
            if a.get('href','').startswith('#'):self.assertIn(a['href'][1:],ids)
    def test_article_order_and_process_embedded_under_methods(self):
        s=self.generate();p=Tags();p.feed(s)
        sections=[a['id'] for a in p.attrs if a.get('id') in ['en-'+v for v in ('brief','literature','methods','unknowns','experiments','sources')]]
        self.assertEqual(sections,['en-'+v for v in ('brief','literature','methods','unknowns','experiments','sources')])
        self.assertLess(s.index('id="en-methods"'),s.index('id="en-process"'))
        self.assertNotIn('从证据到候选方法',s)
    def test_semantic_synthesis_flow_and_support_start_closed(self):
        s=self.generate(localization=self.pack());p=Tags();p.feed(s)
        self.assertIn('synthesis-flow',s);self.assertIn('Synthesis method logic flowchart',s)
        self.assertIn('svg',p.tags);self.assertGreater(p.tags.count('details'),10)
        self.assertFalse(any('open' in a for a in p.attrs))
        self.assertIn('What it tests',s);self.assertIn('What to measure',s);self.assertIn('What it can resolve',s)
    def test_all_scientific_content_retained_in_english_and_unknowns_visible(self):
        from html import escape
        s=self.generate()
        for m in self.data['candidate_methods']:
            for step in m['steps']:
                self.assertIn(escape(step['action']),s)
                for p in step['parameters']:
                    self.assertIn(escape(p['name']),s)
                    for ref in p.get('evidence',[]):self.assertIn(escape(ref['quote']),s)
        for e in self.data['validation_experiments']:
            for key in ('hypothesis','falsification','decision_rule','sample_size_rationale'):self.assertIn(escape(e[key]),s)
            for r in e['readouts']:
                for key in ('metric','method','unit','acceptance','acceptance_basis'):self.assertIn(escape(str(r[key])),s)
        self.assertIn('Unknown',s)
    def test_reference_influence_not_replication_and_missing_not_zero(self):
        s=self.generate(references=dict(documents=[dict(id='PMC4977492',journal='Example journal',citation_count=18,retrieved_at='2026-10-21',provider='Europe PMC')]))
        self.assertIn('Example journal',s);self.assertIn('18',s);self.assertIn('2026-10-21',s)
        self.assertIn('not independent replications',s);self.assertIn('Citing papers have not been checked',s)
        missing=self.generate();self.assertIn('Unknown',missing)
    def test_markdown_compatibility(self):
        self.assertTrue(render(self.source,self.artifact,self.out)['valid'])
        md=self.root/'method.md';render(self.source,self.artifact,md);self.assertTrue(md.read_text().startswith('---'))
    def test_saved_proof_is_rechecked(self):
        (self.root/'execution-evidence.json').write_text('{"verified":true}')
        with patch('biomethod.execution.execution_evidence',return_value={}) as check:
            with self.assertRaises(ValueError):render_job_report(self.root)
            check.assert_called_once()
    def test_curated_demo_zero_models_honest_language_availability(self):
        out=self.root/'demo';self.assertEqual(main(['demo','--out',str(out)]),0)
        self.assertTrue((out/'method.html').is_file());self.assertTrue((out/'method.md').is_file())
        self.assertIn('Full workflow unverified',(out/'method.html').read_text())
