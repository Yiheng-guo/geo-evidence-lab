import copy
import csv
import json
import subprocess
import sys
import tempfile
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
        for row in self.pre + self.post:
            row.pop('recommendation', None)
            row.pop('review_note', None)

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

    def test_manual_recommendation_uses_only_reviewed_pairs(self):
        for rows in (self.pre, self.post):
            rows[0]['recommendation'] = 'recommended'
            rows[0]['review_note'] = '明确建议将该品牌加入候选清单。'
        self.pre[0]['recommendation'] = 'neutral'
        m = self.compare()['metrics']['recommended']
        self.assertEqual(m['denominator'], 1)
        self.assertEqual(m['delta_pp'], 100)

    def test_review_requires_rationale(self):
        self.post[0]['recommendation'] = 'recommended'
        with self.assertRaisesRegex(ValueError, 'review_note'):
            self.compare()

    def test_no_review_is_not_zero_recommendation_rate(self):
        self.assertIsNone(self.compare()['metrics']['recommended']['post_rate'])

    def test_different_engines_are_separate_groups(self):
        self.pre[1]['engine'] = self.post[1]['engine'] = 'second-engine'
        groups = self.compare()['groups']
        self.assertEqual(len(groups), 2)
        self.assertTrue(all(g['metrics']['mentioned']['denominator'] == 1 for g in groups))

    def test_evidence_update_does_not_invalidate_measurement_plan(self):
        self.profile['claims'] = [{'text': '新补充的证据', 'source_url': 'https://example.org/evidence'}]
        self.assertEqual(self.compare()['metrics']['mentioned']['denominator'], 2)

    def test_plan_tampering_is_detected(self):
        self.plan['queries'][0]['text'] = 'edited'
        with self.assertRaisesRegex(ValueError, 'edited'):
            self.compare()

    def test_baseline_with_no_post_data(self):
        report = lab.baseline(self.profile, self.plan, self.pre)
        self.assertEqual(report['status'], 'baseline_only')
        self.assertEqual(report['metrics']['mentioned']['count'], 0)
        self.assertEqual(report['metrics']['mentioned']['denominator'], 3)
        self.assertIn('baseline_only', lab.render(report))

    def test_init_never_overwrites_client_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            lab.init_project(tmp, '新品牌')
            p = Path(tmp) / 'profile.json'
            previous = p.read_bytes()
            with self.assertRaisesRegex(ValueError, 'overwritten'):
                lab.init_project(tmp, '另一个品牌')
            self.assertEqual(p.read_bytes(), previous)

    def test_csv_preserves_multiline_answer_and_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'capture.csv'
            row = dict(self.pre[0])
            row['answer'] = '第一行，含逗号。\n第二行 "引号"。'
            row['citations'] = 'https://example.org/a\nhttps://example.net/b'
            with path.open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=lab.CSV_FIELDS)
                writer.writeheader(); writer.writerow(row)
            records, pending = lab.import_csv(path, self.plan)
            self.assertEqual(records[0]['answer'], row['answer'])
            self.assertEqual(len(records[0]['citations']), 2)
            self.assertEqual(pending, 0)

    def test_pending_template_is_not_observed_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            lab.worksheet(self.plan, tmp, 'engine', 'search', 'fresh', 2)
            records, pending = lab.import_csv(Path(tmp) / 'pre.csv', self.plan)
            self.assertEqual(records, [])
            self.assertEqual(pending, 6)
            with self.assertRaisesRegex(ValueError, 'already exist'):
                lab.worksheet(self.plan, tmp, 'engine', 'search', 'fresh', 2)

    def test_pending_with_answer_requires_status_fix(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'capture.csv'
            row = dict(self.pre[0]); row['status'] = 'pending'; row['citations'] = ''
            with path.open('w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=lab.CSV_FIELDS)
                writer.writeheader(); writer.writerow(row)
            with self.assertRaisesRegex(ValueError, 'pending row contains'):
                lab.import_csv(path, self.plan)

    def test_cli_end_to_end_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            command = [sys.executable, str(ROOT / 'skills/geo-evidence-lab/scripts/geo_lab.py'), 'compare',
                       '--profile', str(ROOT / 'examples/profile.json'), '--plan', str(ROOT / 'examples/plan.json'),
                       '--pre', str(ROOT / 'examples/pre.json'), '--post', str(ROOT / 'examples/post.json'), '--out', tmp]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((Path(tmp) / 'report.json').read_text())
            self.assertEqual(report['status'], 'descriptive_comparison')
            self.assertTrue((Path(tmp) / 'report.html').exists())

    def test_single_question_brief(self):
        text = lab.brief(self.profile, self.plan, 'q001')
        self.assertIn(self.profile['queries'][0], text)
        self.assertNotIn(self.profile['queries'][1], text)
        with self.assertRaisesRegex(ValueError, 'not found'):
            lab.brief(self.profile, self.plan, 'q999')

    def test_legacy_plan_compatibility(self):
        self.plan['schema_version'] = 1
        self.plan['profile_hash'] = lab.fingerprint(self.profile)
        self.assertEqual(self.compare()['metrics']['mentioned']['denominator'], 2)

    def test_getting_started_commands_with_real_csv_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / 'project'
            script = str(ROOT / 'skills/geo-evidence-lab/scripts/geo_lab.py')
            def cli(*args):
                result = subprocess.run([sys.executable, script, *map(str, args)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            cli('init', '--brand', self.profile['brand'], '--out', project)
            profile = project / 'profile.json'; lab.save(profile, self.profile)
            frozen = project / 'plan.json'
            cli('plan', '--profile', profile, '--out', frozen)
            capture = project / 'capture'
            cli('worksheet', '--plan', frozen, '--engine', 'synthetic-engine', '--mode', 'synthetic-search',
                '--context', 'synthetic;fresh-session;zh-CN', '--rounds', 1, '--out', capture)
            for stage, records in [('pre', self.pre), ('post', self.post)]:
                with (capture / (stage + '.csv')).open('w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=lab.CSV_FIELDS); writer.writeheader()
                    for record in records:
                        row = copy.deepcopy(record); row['citations'] = '\n'.join(row['citations'])
                        writer.writerow(row)
                cli('import-csv', '--input', capture / (stage + '.csv'), '--plan', frozen, '--out', project / (stage + '.json'))
            cli('baseline', '--profile', profile, '--plan', frozen, '--input', project / 'pre.json', '--out', project / 'baseline')
            cli('brief', '--profile', profile, '--plan', frozen, '--query-id', 'q001', '--out', project / 'brief.md')
            cli('compare', '--profile', profile, '--plan', frozen, '--pre', project / 'pre.json', '--post', project / 'post.json', '--out', project / 'report')
            report = lab.load(project / 'report/report.json')
            self.assertEqual(report['metrics']['mentioned']['denominator'], 2)
            self.assertEqual(report['metrics']['owned_source_cited']['post_rate'], 0.5)


if __name__ == '__main__':
    unittest.main()
