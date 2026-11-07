import unittest
from manga_ai.engines.contracts import normalize_result

class ResultContractsTests(unittest.TestCase):
 def setUp(self):self.mapping=[{'id':'B001','translation':'Clean','clean':True}]
 def test_review_is_separate_from_skip_even_with_legacy_alias(self):
  r=normalize_result({'overlay':'x','applied':[],'skipped':['B001'],'review_ids':['B001'],'blocked':{'B001':'Needs review'}},self.mapping)
  self.assertEqual(r['region_results'][0]['decision'],'review');self.assertEqual(r['counts'],{'review':1,'skip':0,'applied':0})
 def test_bad_ids_conflicting_decisions_and_missing_decisions_fail(self):
  for result in [dict(overlay='x',applied=['B999'],skipped=[],blocked={}),dict(overlay='x',applied=['B001'],skipped=['B001'],blocked={}),dict(overlay='x',applied=[],skipped=[],blocked={})]:
   with self.assertRaises(ValueError):normalize_result(result,self.mapping)
