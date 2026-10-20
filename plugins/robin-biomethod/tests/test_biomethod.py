"""Negative cases and real upstream wiring; no model capability claims."""
from pathlib import Path
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

PLUGIN=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PLUGIN/'src'),str(PLUGIN/'vendor')]
from biomethod.workflow import prepare, validate_goal, validate_task_source, prompt_lenses
from biomethod.validation import assess, calculate
from biomethod.research import jats_document, search, collect
from biomethod.reporting import compare, render
from biomethod.cli import main
from robinharness.engine import FileTaskAdapter, CodexProposer, run_task
from robinharness.runtime import dump, Budget
from robinharness.cli import optimize


class OfflineRunner:
    model='scripted-offline-no-model'
    def __init__(self,artifact):self.artifact=artifact;self.labels=[]
    def run(self,ws,mission,label,timeout=None):
        self.labels.append(label)
        if label.startswith('execute:'):
            dump(ws/'output/method.json',self.artifact);text='Delivered fixture.'
        elif label.startswith('experience.'):
            text='<edits>component: AGENTS.md\nverdict: no observed effect</edits>\nNO_ENTRY'
        elif label.startswith('select.'):
            text='<why>Equivalent fixture outputs.</why>\n```choice\nA\n```'
        else:text='<notes>KEEP_BASE: no observed failure supports an edit.</notes>'
        return dict(text=text,trajectory='[ACTION] offline fixture\n[OBSERVATION] supplied artifact',usage={})


class BiomethodTests(unittest.TestCase):
    def setUp(self):
        import shutil
        self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name)
        self.example=self.root/'example';shutil.copytree(PLUGIN/'examples/gelma',self.example)
        self.source=self.example/'task/source';self.artifact=self.example/'curated-method.json'
        self.data=json.loads(self.artifact.read_text())
    def tearDown(self):self.t.cleanup()
    def score(self,data=None):
        if data is not None:dump(self.artifact,data)
        return assess(self.source,self.artifact)
    def mutate_fails(self,fn):
        fn(self.data);self.assertFalse(self.score(self.data)['valid'])
    def test_curated_draft_passes_but_never_adoptable(self):
        r=self.score();self.assertTrue(r['valid'],r);self.assertFalse(r['adoptable']);self.assertEqual(r['scientific_validity'],'not experimentally tested')
    def test_false_achievement(self):self.mutate_fails(lambda d:d['target_assessment'].update(status='achieved'))
    def test_false_validated_status(self):self.mutate_fails(lambda d:d.update(status='validated'))
    def test_missing_experiment(self):self.mutate_fails(lambda d:d.update(validation_experiments=[]))
    def test_critical_uncertainty_uncovered(self):self.mutate_fails(lambda d:d['validation_experiments'][0].update(uncertainty_ids=['U1']))
    def test_missing_falsification(self):self.mutate_fails(lambda d:d['validation_experiments'][0].update(falsification=''))
    def test_missing_controls(self):self.mutate_fails(lambda d:d['validation_experiments'][0].update(controls=[]))
    def test_technical_repeats_not_batches(self):self.mutate_fails(lambda d:d['validation_experiments'][0].update(independent_batches=0))
    def test_fabricated_quote(self):self.mutate_fails(lambda d:d['candidate_methods'][0]['steps'][0]['parameters'][0]['evidence'][0].update(quote='invented quotation'))
    def test_missing_locator(self):self.mutate_fails(lambda d:d['candidate_methods'][0]['steps'][0]['parameters'][0]['evidence'][0].update(locator='nonexistent'))
    def test_changed_reported_parameter(self):self.mutate_fails(lambda d:d['candidate_methods'][0]['steps'][0]['parameters'][1].update(value=0.7))
    def test_unit_changed(self):self.mutate_fails(lambda d:d['candidate_methods'][0]['steps'][0]['parameters'][1].update(unit='mL'))
    def test_route_splice(self):self.mutate_fails(lambda d:d['candidate_methods'][0]['steps'][0]['parameters'].append(copy.deepcopy(d['candidate_methods'][1]['steps'][0]['parameters'][0])))
    def test_wrong_arithmetic(self):self.mutate_fails(lambda d:d['candidate_methods'][0]['steps'][1]['parameters'][4].update(value=50))
    def test_arithmetic_code_injection_rejected(self):
        with self.assertRaises(ValueError):calculate('__import__("os").system("id")')
        self.assertEqual(calculate('0.1 * 5'),calculate('0.5'))
    def test_unknown_not_reported_as_complete(self):self.mutate_fails(lambda d:d.update(status='candidate_unvalidated'))
    def test_constraints_coverage(self):self.mutate_fails(lambda d:d.update(constraint_assessments=[]))
    def test_source_drift(self):
        p=self.source/'documents/PMC4977492.txt';p.write_text(p.read_text()+'changed\n');self.assertFalse(self.score()['valid'])
    def test_missing_target_assay_blocks_preparation(self):
        g=json.loads((self.example/'goal.json').read_text());g['target']['assay']=''
        with self.assertRaises(ValueError):validate_goal(g)
    def test_prepare_freezes_source(self):
        result=prepare(self.example/'goal.json',self.example/'bundle',self.example/'method-cards.json',self.root/'prepared',self.example/'profile.json')
        validate_task_source(self.root/'prepared/source');self.assertEqual(result['model_calls'],0)
        with self.assertRaises(ValueError):prepare(self.example/'goal.json',self.example/'bundle',self.example/'method-cards.json',self.root/'prepared')
    def test_malformed_artifact_fails_closed(self):
        self.artifact.write_text('{broken');self.assertFalse(self.score()['valid'])
    def test_abstract_source_rejected(self):
        reg=json.loads((self.source/'registry.json').read_text());reg['documents'][0]['access']='abstract';dump(self.source/'registry.json',reg)
        self.assertFalse(self.score()['valid'])
    def test_compare_never_recommends_chemical_adoption(self):
        bad=self.root/'bad.json';dump(bad,dict(self.data,status='validated'))
        r=compare(self.source,[('base',bad),('candidate',self.artifact)],self.root/'compare.json')
        self.assertFalse(r['recommended']);self.assertFalse(r['comparisons'][0]['assessment']['valid']);self.assertTrue(r['comparisons'][1]['assessment']['valid'])
    def test_renderer_produces_self_contained_method_and_experiment(self):
        out=self.root/'method.md';render(self.source,self.artifact,out);s=out.read_text();self.assertIn('最小验证 E1',s);self.assertIn('PMC4977492',s);self.assertIn('独立合成批次：3',s);self.assertIn('未确定',s)
    def test_discovery_no_model_and_api_dedup(self):
        records={'resultList':{'result':[{'title':'one','doi':'X'},{'title':'duplicate','doi':'x'}]},'hitCount':2}
        with patch('biomethod.research.request',return_value=json.dumps(records).encode()) as req:
            r=search('material synthesis',provider='pubmed');self.assertEqual(len(r['results']),1);self.assertIn('SRC%3AMED',req.call_args[0][0]);self.assertIsNone(r['results'][0]['how'])
    def test_fulltext_xml_tables_and_missing_supplements(self):
        xml=b'<article><front><article-title>Method</article-title></front><body><sec><title>Methods</title><p>Mix carefully.</p><table-wrap><label>T1</label><table><tr><td>time</td><td>1 h</td></tr></table></table-wrap></sec></body></article>'
        doc,text=jats_document('PMC1',xml);self.assertIn('time | 1 h',text);self.assertIn('not retrieved',doc['supplement_status'])
        with self.assertRaises(ValueError):jats_document('PMC1',b'<article><front><abstract>Abstract only</abstract></front></article>')
    def test_collection_failure_is_incomplete(self):
        with patch('biomethod.research.request',side_effect=TimeoutError('network unavailable')):
            r=collect(['PMC1'],self.root/'collection');self.assertEqual(r['status'],'incomplete');self.assertEqual(r['documents'],0)
    def test_upstream_k1_k2_and_dimension_lenses(self):
        for k in (1,2):
            runner=OfflineRunner(self.data);root=self.root/f'k{k}'
            adapter=FileTaskAdapter(self.example/'task/task.json',root,runner)
            self.assertIn('process failure',adapter.spec.prompts.inv_levers)
            self.assertIn('material profile',adapter.spec.prompts.dom_levers)
            result=run_task(adapter,CodexProposer(runner,root/'editors'),k=k)
            self.assertEqual(result.status,'ok',result.errors)
            self.assertTrue(any(x.startswith('dom') for x in runner.labels))
            self.assertEqual(any(x.startswith('select.') for x in runner.labels),k>1)
    def test_domain_optimize_never_enables_adoption(self):
        from types import SimpleNamespace
        with patch('robinharness.cli.CodexRunner',return_value=OfflineRunner(self.data)):
            args=SimpleNamespace(task=str(self.example/'task/task.json'),run_dir=str(self.root/'run'),k=1,session_limit=16,minutes=45,model=None,holdout=[],learning_task=None,mode='parallel',library_dir=None)
            report,run=optimize(args);self.assertEqual(report['status'],'completed',report['errors']);self.assertFalse(report['recommended']);self.assertEqual(report['scientific_performance'],'not experimentally tested')
    def test_document_improvement_still_cannot_recommend_adoption(self):
        from types import SimpleNamespace
        import shutil
        held=self.root/'held';shutil.copytree(self.example/'task',held)
        task=json.loads((held/'task.json').read_text());task['id']='held-document-fixture';dump(held/'task.json',task)
        goal=json.loads((held/'source/goal.json').read_text());goal['application']='Distinct scripted document-quality fixture, NOT an independent scientific validation';dump(held/'source/goal.json',goal)
        class QualityRunner(OfflineRunner):
            def run(runner,ws,mission,label,timeout=None):
                result=super(QualityRunner,runner).run(ws,mission,label,timeout)
                if label=='execute:baseline':
                    bad=copy.deepcopy(self.data);bad['status']='validated';dump(ws/'output/method.json',bad)
                return result
        with patch('robinharness.cli.CodexRunner',return_value=QualityRunner(self.data)):
            args=SimpleNamespace(task=str(self.example/'task/task.json'),run_dir=str(self.root/'quality-run'),k=1,session_limit=16,minutes=45,model=None,holdout=[str(held/'task.json')],learning_task=None,mode='parallel',library_dir=None)
            report,_=optimize(args)
            self.assertEqual(report['status'],'completed',report['errors']);self.assertTrue(report['document_quality_improvement']);self.assertFalse(report['recommended'])
    def test_material_neutral_preparation_and_execution(self):
        # Deliberately synthetic second material: proves routing, not chemistry transfer.
        source=self.root/'synthetic';(source/'documents').mkdir(parents=True)
        text='[L1] Synthetic fixture route uses 2 g of precursor.\n';(source/'documents/D1.txt').write_text(text)
        dump(source/'registry.json',dict(documents=[dict(id='D1',title='Synthetic test, not a paper',url='https://example.org/synthetic-test',access='curated_excerpt',text_file='documents/D1.txt',sha256=hashlib.sha256(text.encode()).hexdigest())]))
        g=json.loads((self.example/'goal.json').read_text());g.update(material='SyntheticMaterial-X',constraints=[])
        dump(self.root/'goal.json',g)
        ev=[dict(document='D1',locator='L1',quote='2 g')]
        dump(self.root/'cards.json',[dict(id='R1',document='D1',name='Synthetic route',parameters=[dict(name='feed_mass',value=2,unit='g',evidence=ev)],limitations=['Synthetic test only'])])
        prepare(self.root/'goal.json',source,self.root/'cards.json',self.root/'generic')
        lenses=prompt_lenses(self.root/'generic/source')
        self.assertNotIn('GelMA',json.dumps(lenses));self.assertNotIn('dialysis-clearance',json.dumps(lenses))
        artifact=copy.deepcopy(self.data);artifact.update(material='SyntheticMaterial-X',constraint_assessments=[])
        artifact['candidate_methods']=[dict(id='M-A',route_id='R1',inputs=['synthetic precursor'],steps=[dict(action='Synthetic fixture step',parameters=[dict(name='feed_mass',value=2,unit='g',evidence=ev,origin='reported')])],checkpoints=['synthetic check'],characterization=['synthetic assay'],gaps=['No chemical evidence; test fixture'])]
        artifact['validation_experiments'][0]['method_ids']=['M-A'];artifact['validation_experiments'][0]['uncertainty_ids']=['U1','U2','U3']
        dump(self.root/'generic-artifact.json',artifact)
        self.assertTrue(assess(self.root/'generic/source',self.root/'generic-artifact.json')['valid'])
        runner=OfflineRunner(artifact);adapter=FileTaskAdapter(self.root/'generic/task.json',self.root/'generic-run',runner)
        self.assertEqual(run_task(adapter,CodexProposer(runner,self.root/'generic-editors')).status,'ok')
    def test_nonfinite_goal_rejected(self):
        g=json.loads((self.example/'goal.json').read_text());g['target']['value']=float('inf')
        with self.assertRaises(ValueError):validate_goal(g)
    def test_merge_preserves_source_identity_and_rejects_duplicates(self):
        from biomethod.research import merge_collections
        with self.assertRaises(ValueError):merge_collections([self.example/'bundle',self.example/'bundle'],self.root/'duplicate')
        self.assertFalse((self.root/'duplicate').exists())
        r=merge_collections([self.example/'bundle'],self.root/'merged');self.assertEqual(r['documents'],2)
        from biomethod.workflow import source_index
        self.assertEqual(len(source_index(self.root/'merged')[0]),2)
    def test_product_cli_has_no_adopt_command(self):
        from contextlib import redirect_stderr
        from io import StringIO
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):main(['adopt'])

if __name__=='__main__':unittest.main()
