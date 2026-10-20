"""Workflow regressions. Scripted fixtures are never live-model acceptance evidence."""
from pathlib import Path
import hashlib
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PLUGIN=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PLUGIN/'src'),str(PLUGIN/'vendor')]
from biomethod.pipeline import run_design, settings, minimum_sessions, model_json, job_status
from biomethod.execution import execution_evidence, export_execution
from biomethod.workflow import validate_goal
from biomethod.validation import assess
from robinharness.runtime import dump
from test_biomethod import OfflineRunner

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.env=patch.dict(os.environ,ROBINBIOMETHOD_HOME=str(self.root/'state'));self.env.start()
        self.example=PLUGIN/'examples/gelma'
        self.goal=json.loads((self.example/'goal.json').read_text())
        self.gpath=self.root/'goal.json';dump(self.gpath,self.goal)
        self.cards=json.loads((self.example/'method-cards.json').read_text())
        self.profile=json.loads((self.example/'profile.json').read_text())
        self.artifact=json.loads((self.example/'curated-method.json').read_text())
        self.extracted=dict(method_cards=self.cards,profile=self.profile,literature_review=[dict(document=c['document'],why='fixture relevance',how='fixture method',what='fixture limits',method_evidence=c['parameters'][0]['evidence']) for c in self.cards],source_gaps=['fixture only'])
    def tearDown(self):self.env.stop();self.temp.cleanup()
    def runner(self,budget,audit,model):
        outer=self
        class Fixture(OfflineRunner):
            def run(self,ws,mission,label,timeout=None):
                i,_=budget.reserve(label)
                if getattr(outer,'fail_final',False) and label.endswith('/agg1'):
                    budget.finish(i,state='failed',error='out of credits');raise RuntimeError('out of credits')
                if label.startswith('screening.'):
                    dump(ws/'output/result.json',dict(selected=[dict(pmcid='PMC4977492',reason='fixture')],limitations=[]));r=dict(text='fixture',usage={})
                elif label.startswith('method-extraction.'):
                    dump(ws/'output/result.json',outer.extracted);r=dict(text='fixture',usage={})
                elif label.startswith('delivery-repair.'):
                    patch_data=dict(expressions=[dict(method_id=m['id'],step=si,parameter=pi,expression=p['expression']) for m in outer.repaired['candidate_methods'] for si,step in enumerate(m['steps']) for pi,p in enumerate(step['parameters']) if p['origin']=='calculated'],validation_experiments=outer.repaired['validation_experiments'])
                    if outer.repaired['material']!=outer.artifact['material']:patch_data['material']=outer.repaired['material']
                    dump(ws/'output/result.json',patch_data);r=dict(text='synthetic repair fixture',usage={})
                else:
                    if label.endswith('/agg1') and (ws/'output/method.json').exists():outer.seed_seen=True
                    r=super().run(ws,mission,label,timeout)
                    if label.startswith('experience.') and getattr(outer,'save_experience',False):r['text']='<experience>cue: fixture task\nlesson: Keep evidence checks scoped\nevidence: observed fixture links\nconfidence: low</experience>'
                if getattr(outer,'synthetic_trace',False):
                    # Synthetic protocol trace for tamper tests; NOT live acceptance.
                    audit.mkdir(exist_ok=True)
                    raw=json.dumps(dict(type='turn.completed'))+'\n'+json.dumps(dict(type='item.completed',item=dict(type='agent_message',text='synthetic fixture')))+'\n'
                    (audit/f'{i:03d}.jsonl').write_text(raw)
                    budget.finish(i,state='ok',transport='codex_cli',audit_sha256=hashlib.sha256(raw.encode()).hexdigest())
                else:budget.finish(i,state='ok',transport='scripted_fixture')
                return dict(r,audit_index=i)
        return Fixture(self.artifact)
    def design(self,**kw):
        return run_design(self.gpath,bundle=self.example/'bundle',run_dir=self.root/'job',runner_factory=self.runner,**kw)
    def test_default_budget_and_minimum(self):
        self.assertEqual(settings()['session_limit'],16)
        self.assertEqual(minimum_sessions(1),10);self.assertEqual(minimum_sessions(1,True),9)
        self.assertEqual(minimum_sessions(2),18)
    def test_budget_custom_not_fixed_ceiling(self):
        self.assertEqual(settings(dict(session_limit=100,minutes=90))['minutes'],90)
    def test_invalid_budget(self):
        for args in (dict(session_limit=0),dict(minutes=float('inf')),dict(minutes=True),dict(k=4)):
            with self.subTest(args=args),self.assertRaises(ValueError):settings(args)
    def test_underfunded_no_model(self):
        with self.assertRaises(ValueError):self.design(overrides=dict(session_limit=8))
        self.assertFalse((self.root/'job').exists())
    def test_dryrun_never_execution(self):
        r=self.design(dry_run=True)
        self.assertEqual(r['model_calls'],0);self.assertFalse(r['workflow_complete']);self.assertFalse((self.root/'job').exists())
    def test_unknown_tolerance_requires_declaration(self):
        self.goal['target']['tolerance']=None
        with self.assertRaises(ValueError):validate_goal(self.goal)
        self.goal['unknown_fields']=['target.tolerance'];validate_goal(self.goal)
    def test_unknown_forces_draft(self):
        shutil.copytree(self.example/'task/source',self.root/'source')
        self.goal['unknown_fields']=['available_equipment'];dump(self.root/'source/goal.json',self.goal)
        self.artifact['status']='candidate_unvalidated';dump(self.root/'method.json',self.artifact)
        self.assertFalse(assess(self.root/'source',self.root/'method.json')['valid'])
    def test_shared_budget_reaches_original_core_but_fixture_cannot_pass(self):
        r=self.design();j=job_status(self.root/'job')
        self.assertFalse(r['workflow_complete']);self.assertEqual(r['model_sessions_attempted'],9)
        self.assertEqual(j['stages']['freeze']['state'],'completed')
        proof=execution_evidence(self.root/'job/harness',self.root/'job/budget.json',self.root/'job/audit')
        self.assertEqual(len(proof['stages']),4);self.assertEqual(len(proof['rule_edits']),3)
        self.assertFalse(proof['verified']);self.assertFalse(proof['core_executed'])
        self.assertEqual(j['stages']['discovery']['state'],'completed_external_input')
    def test_native_screening_and_collection(self):
        def collected(ids,out,search):
            shutil.copytree(self.example/'bundle',out)
            return dict(documents=2,errors=[])
        with patch('biomethod.pipeline.search',return_value=dict(results=[dict(pmcid='PMC4977492')])),patch('biomethod.pipeline.collect',side_effect=collected):
            r=run_design(self.gpath,run_dir=self.root/'job',runner_factory=self.runner)
        self.assertEqual(r['model_sessions_attempted'],10)
        self.assertEqual(job_status(self.root/'job')['stages']['screening']['state'],'completed')
    def test_network_failure_preserved_without_models(self):
        with patch('biomethod.pipeline.search',side_effect=TimeoutError('DNS unavailable')):
            r=run_design(self.gpath,run_dir=self.root/'job',runner_factory=self.runner)
        self.assertEqual(r['model_sessions_attempted'],0);self.assertFalse(r['workflow_complete'])
        self.assertIn('DNS',r['errors'][0]);self.assertTrue((self.root/'job/workflow.json').exists())
    def test_no_fulltext_candidates(self):
        with patch('biomethod.pipeline.search',return_value=dict(results=[])):
            r=run_design(self.gpath,run_dir=self.root/'job',runner_factory=self.runner)
        self.assertEqual(r['model_sessions_attempted'],0);self.assertFalse(r['harness2_executed'])
    def test_fabricated_extraction_quote_rejected(self):
        self.extracted['method_cards'][0]['parameters'][0]['evidence'][0]['quote']='invented'
        r=self.design();self.assertEqual(r['model_sessions_attempted'],2)
        self.assertEqual(job_status(self.root/'job')['stages']['freeze']['state'],'pending')
    def test_unknown_source_id_rejected(self):
        self.extracted['literature_review'][0]['method_evidence'][0]['document']='FAKE'
        r=self.design();self.assertEqual(r['model_sessions_attempted'],2);self.assertFalse(r['workflow_complete'])
    def test_account_failure_preserved(self):
        def factory(budget,audit,model):
            class Failed:
                def run(self,ws,mission,label):
                    i,_=budget.reserve(label);budget.finish(i,state='failed',error='out of credits')
                    raise RuntimeError('out of credits')
            return Failed()
        r=run_design(self.gpath,bundle=self.example/'bundle',run_dir=self.root/'job',runner_factory=factory)
        self.assertEqual(r['model_sessions_attempted'],1);self.assertIn('out of credits',r['errors'][0])
    def test_missing_report_not_execution(self):
        r=execution_evidence(self.root);self.assertFalse(r['verified'])
    def test_corrupt_report_exports_incomplete(self):
        (self.root/'report.json').write_text('{broken')
        r=export_execution(self.root);self.assertFalse(r['verified']);self.assertEqual(r['status'],'incomplete')
        self.assertTrue((self.root/'execution-report.md').exists())
    def test_missing_audit_does_not_trust_completed_report(self):
        dump(self.root/'report.json',dict(status='completed',budget=dict(sessions=[dict(state='ok',transport='codex_cli')]),upstream_result=dict(status='ok')))
        self.assertFalse(execution_evidence(self.root)['verified'])
    def test_trace_fixture_binding_and_tampering(self):
        self.synthetic_trace=True
        r=self.design()
        self.assertTrue(r['workflow_complete'],r)
        run=self.root/'job/harness';bp=self.root/'job/budget.json';ad=self.root/'job/audit'
        proof=execution_evidence(run,bp,ad)
        self.assertTrue(proof['verified'],proof)
        self.assertTrue(execution_evidence(run)['verified'])
        self.assertTrue((self.root/'job/literature-review.md').exists())
        self.assertTrue((self.root/'job/candidate-method.md').exists())
        html=(self.root/'job/report.html').read_text()
        self.assertIn('fixture relevance',html);self.assertIn('最小验证实验',html)
        self.assertEqual(Path(r['html_report']).resolve(),(self.root/'job/report.html').resolve())
        artifact=Path(proof['stages'][0]['artifact']);original=artifact.read_text()
        artifact.write_text(original+' ')
        self.assertFalse(execution_evidence(run,bp,ad)['verified'])
        artifact.write_text(original)
        trace=ad/'000.jsonl';trace.write_text('tampered')
        # Extraction transport is not a core stage; tamper an actual executor trace.
        index=proof['stages'][0]['session_indices'][0]
        (ad/f'{index:03d}.jsonl').write_text('tampered')
        self.assertFalse(execution_evidence(run,bp,ad)['verified'])
    def test_corrupt_receipt_fails_closed(self):
        self.synthetic_trace=True;self.design()
        run=self.root/'job/harness';proof=execution_evidence(run,self.root/'job/budget.json',self.root/'job/audit')
        receipt=Path(proof['stages'][0]['artifact']).parent.parent/'execution.json'
        receipt.write_text('{broken')
        self.assertFalse(export_execution(run,self.root/'job/budget.json',self.root/'job/audit')['verified'])

    def test_prepared_recovery_does_not_redo_preparation(self):
        self.design()
        with self.assertRaises(ValueError):run_design(self.gpath,prepared_from=self.root/'job',run_dir=self.root/'retry',overrides=dict(session_limit=7,minutes=30),dry_run=True)
        # The prior fixture used9 of16;7 remaining cannot fund8 core calls.

    def test_prepared_recovery_rejects_changed_goal(self):
        self.design();self.goal['material']='changed';dump(self.gpath,self.goal)
        with self.assertRaises(ValueError):run_design(self.gpath,prepared_from=self.root/'job',dry_run=True)
    def test_prepared_recovery_rejects_changed_source(self):
        self.design();g=self.root/'job/task/source/goal.json';g.write_text(g.read_text()+' ')
        with self.assertRaises(ValueError):run_design(self.gpath,prepared_from=self.root/'job',dry_run=True)
    def test_recovery_only_consumes_core_calls(self):
        self.design(overrides=dict(session_limit=24,minutes=45))
        self.synthetic_trace=True
        r=run_design(self.gpath,prepared_from=self.root/'job',run_dir=self.root/'retry',overrides=dict(session_limit=15,minutes=30),runner_factory=self.runner)
        self.assertTrue(r['workflow_complete'],r);self.assertEqual(r['model_sessions_attempted'],8)
        labels=[x['label'] for x in json.loads((self.root/'retry/budget.json').read_text())['sessions']]
        self.assertFalse(any(x.startswith('method-extraction') or x.startswith('screening') for x in labels))

    def test_post_core_repair_preserves_original_artifact(self):
        self.synthetic_trace=True;self.repaired=copy.deepcopy(self.artifact)
        for m in self.artifact['candidate_methods']:
            for step in m['steps']:
                for p in step['parameters']:
                    if p['origin']=='calculated':p['expression']='invalid units'
        r=self.design();self.assertTrue(r['workflow_complete'],r)
        proof=execution_evidence(self.root/'job/harness')
        self.assertFalse(proof['selected_assessment']['valid']);self.assertTrue(proof['delivery_repair_executed'])
        self.assertTrue(proof['delivery_assessment']['valid']);self.assertEqual(r['model_sessions_attempted'],10)
        Path(proof['delivery_artifact']).write_text('{}')
        self.assertFalse(execution_evidence(self.root/'job/harness')['verified'])
    def test_delivery_repair_cannot_change_scientific_values(self):
        self.synthetic_trace=True;self.repaired=copy.deepcopy(self.artifact)
        for m in self.artifact['candidate_methods']:
            for step in m['steps']:
                for p in step['parameters']:
                    if p['origin']=='calculated':p['expression']='invalid units'
        self.repaired['material']='changed material'
        r=self.design();self.assertFalse(r['workflow_complete']);self.assertEqual(r['model_sessions_attempted'],11)
        self.assertIn('changed original scientific content',r['errors'][0])
    def test_public_checker_detects_real_observed_failure_modes(self):
        shutil.copytree(self.example/'task/source',self.root/'source')
        (self.root/'scripts').mkdir();shutil.copy2(PLUGIN/'assets/base/scripts/check_method.py',self.root/'scripts/check_method.py')
        for m in self.artifact['candidate_methods']:
            for step in m['steps']:
                for p in step['parameters']:
                    if p['origin']=='calculated':p['expression']='25 mL * 2 = 50 mL'
        self.artifact['validation_experiments'][0]['uncertainty_ids']=[]
        dump(self.root/'method.json',self.artifact)
        result=subprocess.run([sys.executable,'scripts/check_method.py','method.json'],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(result.returncode,1);self.assertIn('invalid arithmetic',result.stdout);self.assertIn('critical uncertainties',result.stdout)

    def test_review_identity_cannot_disagree_with_valid_quote(self):
        self.extracted['literature_review'][0]['document']='FAKE'
        r=self.design();self.assertFalse(r['workflow_complete']);self.assertEqual(r['model_sessions_attempted'],2)

    def test_native_tail_recovery_does_not_rerun_prior_stages(self):
        from biomethod.resume import resume_final
        self.synthetic_trace=True;self.fail_final=True
        first=self.design(overrides=dict(session_limit=24))
        self.assertFalse(first['workflow_complete']);self.assertEqual(first['model_sessions_attempted'],8)
        self.fail_final=False;self.save_experience=True
        result=resume_final(self.root/'job',minutes=30,runner_factory=self.runner)
        self.assertTrue(result['workflow_complete'],result);self.assertEqual(result['model_sessions_attempted'],10)
        self.assertTrue(execution_evidence(self.root/'job/harness')['verified'])
        self.assertTrue(list((self.root/'job/harness/library').rglob('EXPERIENCE.md')))
    def test_native_tail_recovery_preserves_account_failure(self):
        from biomethod.resume import resume_final
        self.synthetic_trace=True;self.fail_final=True;self.design(overrides=dict(session_limit=24))
        result=resume_final(self.root/'job',minutes=30,runner_factory=self.runner)
        self.assertFalse(result['workflow_complete']);self.assertEqual(result['model_sessions_attempted'],9)
        self.assertIn('out of credits',result['errors'][-1])
        self.assertTrue((self.root/'job/final-recovery-history/report.json').exists())
    def test_native_tail_recovery_checks_budget_and_saved_proposal(self):
        from biomethod.resume import resume_final
        self.synthetic_trace=True;self.fail_final=True;self.design(overrides=dict(session_limit=24))
        with self.assertRaises(ValueError):resume_final(self.root/'job',minutes=90,runner_factory=self.runner)
        work=next((self.root/'job/harness/primary/runs').rglob('summary.json')).parent
        f=work/'harnesses/agg1/AGENTS.md';f.write_text(f.read_text()+'\nChanged outside proposal.\n')
        with self.assertRaises(ValueError):resume_final(self.root/'job',minutes=30,runner_factory=self.runner)

    def test_explicit_extension_and_partial_seed_preserve_stage_history(self):
        from biomethod.resume import resume_final
        self.synthetic_trace=True;self.fail_final=True;self.design(overrides=dict(session_limit=24))
        resume_final(self.root/'job',minutes=30,runner_factory=self.runner)
        folder=self.root/'job/partial-recovered';folder.mkdir()
        dump(folder/'method.json',self.artifact)
        digest=hashlib.sha256((folder/'method.json').read_bytes()).hexdigest()
        dump(folder/'recovery.json',dict(method_sha256=digest,transport_completed=False))
        self.fail_final=False
        result=resume_final(self.root/'job',minutes=45,extra_minutes=15,reuse_partial=True,runner_factory=self.runner)
        self.assertTrue(result['workflow_complete'],result);self.assertTrue(self.seed_seen)
        self.assertEqual(result['model_sessions_attempted'],11)
        self.assertEqual(result['settings']['minutes'],60)
        self.assertTrue((self.root/'job/final-recovery-history-002').exists())
        proof=execution_evidence(self.root/'job/harness')
        final=next(x for x in proof['stages'] if x['label']=='agg1')
        receipt=json.loads((Path(final['artifact']).parent.parent/'execution.json').read_text())
        self.assertEqual(receipt['continuation_seed_sha256'],digest)
    def test_partial_seed_hash_must_match(self):
        from biomethod.resume import resume_final
        self.synthetic_trace=True;self.fail_final=True;self.design(overrides=dict(session_limit=24))
        folder=self.root/'job/partial-recovered';folder.mkdir();dump(folder/'method.json',self.artifact)
        dump(folder/'recovery.json',dict(method_sha256='wrong'))
        with self.assertRaises(ValueError):resume_final(self.root/'job',minutes=30,reuse_partial=True,runner_factory=self.runner)
        self.assertEqual(len(json.loads((self.root/'job/budget.json').read_text())['sessions']),8)

    def test_routing_contract(self):
        setup=(PLUGIN/'skills/biomethod-setup/SKILL.md').read_text()
        design=(PLUGIN/'skills/biomethod-design/SKILL.md').read_text()
        self.assertIn('hand off to biomethod-design',setup)
        self.assertIn('FULL-HARNESS mode by default',design)
        self.assertIn('workflow_complete=true',design);self.assertIn('verified=true',design)
        self.assertIn('Only an explicit user request',design)

if __name__=='__main__':unittest.main()
