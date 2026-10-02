import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('geo_lab', ROOT / 'skills/geo-evidence-lab/scripts/geo_lab.py')
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.profile = lab.load(ROOT / 'examples/profile.json')
        self.plan = lab.plan(self.profile)
        self.pre = lab.load(ROOT / 'examples/pre.json')
        self.post = lab.load(ROOT / 'examples/post.json')

    def compare(self):
        return lab.compare(self.profile, self.plan, self.pre, self.post)

    def test_failure_excluded_from_denominator(self):
        report = self.compare()
        self.assertEqual(report['metrics']['mentioned']['denominator'], 2)
        self.assertEqual(report['metrics']['mentioned']['delta_pp'], 100)
        self.assertEqual(report['metrics']['owned_source_cited']['delta_pp'], 50)
        self.assertEqual(report['missing_queries'], ['q003'])

    def test_empty_data_is_not_success(self):
        self.pre, self.post = [], []
        report = self.compare()
        self.assertEqual(report['status'], 'not_comparable')
        self.assertIsNone(report['metrics']['mentioned']['post_rate'])
        self.assertEqual(len(report['missing_queries']), 3)

    def test_changed_context_not_paired(self):
        self.post[0]['context'] = 'different-session'
        self.assertEqual(self.compare()['metrics']['mentioned']['denominator'], 1)

    def test_duplicate_rejected(self):
        self.pre.append(copy.deepcopy(self.pre[0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.compare()

    def test_changed_query_rejected(self):
        self.post[0]['query'] = 'a new easier question'
        with self.assertRaisesRegex(ValueError, 'frozen'):
            self.compare()

    def test_changed_profile_rejected(self):
        self.profile['aliases'].append('another brand')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.compare()

    def test_reverse_time_rejected(self):
        self.post[0]['captured_at'] = self.pre[0]['captured_at']
        with self.assertRaisesRegex(ValueError, 'later'):
            self.compare()

    def test_missing_timezone_rejected(self):
        self.pre[0]['captured_at'] = '2026-10-01T10:00:00'
        with self.assertRaisesRegex(ValueError, 'timezone'):
            self.compare()

    def test_domain_spoof_and_subdomain(self):
        row = {'answer': '示例协作云', 'citations': ['https://example.org.evil.test/']}
        self.assertFalse(lab.measure(row, self.profile)['owned_source_cited'])
        row['citations'] = ['https://docs.example.org/guide']
        self.assertTrue(lab.measure(row, self.profile)['owned_source_cited'])

    def test_ascii_alias_boundaries(self):
        self.assertFalse(lab.mention('DemoCollabology', 'DemoCollab'))
        self.assertTrue(lab.mention('Try DEMOCOLLAB.', 'DemoCollab'))

    def test_html_in_answer_is_inert(self):
        self.post[0]['answer'] = '<script>alert(1)</script>示例协作云'
        rendered = lab.render(self.compare())
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)

    def test_javascript_citation_rejected(self):
        self.post[0]['citations'] = ['javascript:alert(1)']
        with self.assertRaisesRegex(ValueError, 'HTTP'):
            self.compare()


if __name__ == '__main__':
    unittest.main()
