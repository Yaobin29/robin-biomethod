"""Metadata failure stays unknown and exact source identity is checked."""
from pathlib import Path
import json,sys,tempfile,unittest
from unittest.mock import patch
PLUGIN=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PLUGIN/'src'),str(PLUGIN/'vendor')]
from biomethod.reference_profile import refresh_references

class Response:
    def __init__(self,value):self.value=value
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,*args):return json.dumps(self.value).encode()

class ReferenceProfileTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name)
        (self.root/'registry.json').write_text(json.dumps(dict(documents=[dict(id='PMC1',doi='10.example/exact')])) )
    def tearDown(self):self.t.cleanup()
    def result(self,records):
        payload=dict(resultList=dict(result=records))
        with patch('biomethod.reference_profile.urlopen',return_value=Response(payload)):
            return refresh_references(self.root,self.root/'profile.json')['documents'][0]
    def test_dated_exact_match_count_not_replication(self):
        r=self.result([dict(pmcid='PMC1',doi='10.example/exact',citedByCount=18,journalInfo=dict(journal=dict(title='Test journal')),pubYear='2024')])
        self.assertEqual(r['citation_count'],18);self.assertEqual(r['journal'],'Test journal')
        self.assertIn('retrieved_at',r);self.assertEqual(r['independent_replication'],'not assessed')
    def test_failed_lookup_is_unknown_not_zero(self):
        with patch('biomethod.reference_profile.urlopen',side_effect=OSError('offline')):
            r=refresh_references(self.root,self.root/'profile.json')['documents'][0]
        self.assertIsNone(r['citation_count']);self.assertEqual(r['status'],'unavailable')
    def test_mismatched_source_and_invalid_count_rejected(self):
        for records in [[dict(pmcid='PMC2',doi='10.example/other',citedByCount=99)],[dict(pmcid='PMC1',doi='10.example/exact',citedByCount=-1)]]:
            r=self.result(records);self.assertIsNone(r['citation_count']);self.assertEqual(r['status'],'unavailable')
