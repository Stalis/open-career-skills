import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from scripts.application import initialize
from scripts import review_cycle as rc


class ReviewCycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.app = initialize(self.root, 'Example', 'Backend', 'https://jobs.example/1')
        (self.app / 'cv.md').write_text('# Example\nBuilt REST APIs in C#.\n')
        (self.app / 'job.md').write_text('# JD\nCoverage: complete\nC# and REST required.\n')
        self.facts = self.app / 'facts.md'
        self.facts.write_text('S1: candidate confirmed C# REST APIs.\n')
        self.profile = self.root / 'profile' / 'profile.md'
        self.profile.parent.mkdir()
        self.profile.write_text('Built REST APIs in C#.\n')
        self.status_before = (self.app / 'status.md').read_bytes()
        self.tracker = self.root / 'tracker' / 'applications.md'
        self.tracker.parent.mkdir()
        self.tracker.write_text('Private existing tracker\n')

    def start(self, **kwargs):
        return rc.start(self.app, root=self.root, **kwargs)

    def snapshot(self):
        return rc.snapshot(self.app, self.facts, [self.profile], root=self.root)

    def status(self):
        return rc.inspect(self.app, root=self.root)

    def receipt(self, outcome='passed', reviewer=None):
        state = self.status()
        return {'manifest_sha256': state['manifest_sha256'], 'outcome': outcome,
                'reviewer_id': reviewer or f"agent-{state['cycle']}-{state['round']}",
                'package_complete': outcome not in rc.FAILURES,
                'report': 'Full synthetic critique. No unsupported claims found.',
                'summary': 'Synthetic summary.', 'findings': [], 'decisions': [],
                'questions': ['Describe your relevant experience.'] if outcome == 'needs_input' else []}

    def record(self, outcome='passed', receipt=None):
        return rc.record(self.app, receipt or self.receipt(outcome), root=self.root)

    def test_snapshot_resume_and_immutable_results(self):
        self.start()
        state = self.snapshot()
        rnd = self.app / 'review-cycles/001/rounds/001'
        self.assertEqual((rnd / 'cv.md').read_bytes(), (self.app / 'cv.md').read_bytes())
        self.assertEqual(state, self.status())
        with self.assertRaises(ValueError):
            self.snapshot()
        result = self.record()
        self.assertTrue(result['current'])
        self.assertEqual(result['state'], 'passed')
        before = (rnd / 'result/result.json').read_bytes()
        with self.assertRaises(ValueError):
            self.record()
        self.assertEqual(before, (rnd / 'result/result.json').read_bytes())
        self.assertIn('Full synthetic critique', (rnd / 'result/report.md').read_text())
        self.assertIn('result/report.md', (self.app / 'review.md').read_text())

    def test_three_reviews_cap_and_no_unreviewed_fourth(self):
        self.start()
        for number in range(1, 4):
            (self.app / 'cv.md').write_text(f'C# REST API developer. Revision {number}.')
            self.assertEqual(self.snapshot()['round'], number)
            state = self.record('revise')
        self.assertEqual(state['state'], 'limit_reached')
        self.assertEqual(state['stop_reason'], 'limit_reached')
        with self.assertRaises(ValueError):
            self.snapshot()
        with self.assertRaises(ValueError):
            self.start()

    def test_changed_cv_job_bundle_and_provenance_invalidate(self):
        self.start()
        self.snapshot()
        self.record()
        for path in (self.app / 'cv.md', self.app / 'job.md', self.facts, self.profile):
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_bytes(original + b'Changed\n')
                self.assertFalse(self.status()['current'])
                self.assertTrue(self.status()['changes'])
                path.write_bytes(original)
                self.assertTrue(self.status()['current'])
        self.profile.unlink()
        self.assertFalse(self.status()['current'])

    def test_stale_pending_review_cannot_pass(self):
        self.start()
        self.snapshot()
        (self.app / 'cv.md').write_text('Changed CV')
        with self.assertRaises(ValueError):
            self.record()
        state = self.record('incomplete_package')
        self.assertEqual(state['state'], 'incomplete_package')
        self.assertIsNone(state['reviewed_cv'])

    def test_new_facts_preserve_old_history(self):
        self.start()
        self.snapshot()
        self.record('needs_input')
        old = {str(p.relative_to(self.app)): p.read_bytes() for p in (self.app / 'review-cycles/001').rglob('*') if p.is_file()}
        answer = self.app / 'answer.md'
        answer.write_text('Q1: I implemented integration tests; candidate confirmed.')
        self.facts.write_text(self.facts.read_text() + answer.read_text())
        self.assertEqual(self.start(reason='new_facts', evidence=answer)['cycle'], 2)
        self.assertEqual(self.snapshot()['round'], 1)
        for name, content in old.items():
            self.assertEqual((self.app / name).read_bytes(), content)
        self.assertEqual((self.app / 'review-cycles/002/restart-evidence.md').read_bytes(), answer.read_bytes())

    def test_restarts_require_stopped_cycle_and_recorded_request(self):
        self.start()
        answer = self.app / 'answer.md'
        answer.write_text('Continue review explicitly.')
        with self.assertRaises(ValueError):
            self.start(reason='user_requested', evidence=answer)
        self.snapshot()
        self.record('plateau')
        with self.assertRaises(ValueError):
            self.start(reason='user_requested')
        self.assertEqual(self.start(reason='user_requested', evidence=answer)['cycle'], 2)

    def test_no_application_or_tracker_status_changes(self):
        self.start()
        self.snapshot()
        self.record()
        self.assertEqual(self.status_before, (self.app / 'status.md').read_bytes())
        self.assertEqual(self.tracker.read_text(), 'Private existing tracker\n')

    def test_failure_and_incomplete_package_do_not_pass(self):
        self.start()
        self.snapshot()
        result = self.receipt()
        result['package_complete'] = False
        with self.assertRaises(ValueError):
            self.record(receipt=result)
        result = self.receipt('review_unavailable')
        result['reviewer_id'] = None
        state = self.record(receipt=result)
        self.assertEqual(state['state'], 'review_unavailable')
        self.assertIsNone(state['reviewed_cv'])
        with self.assertRaises(ValueError):
            self.snapshot()

    def test_pass_rejects_material_findings_and_questions(self):
        self.start()
        self.snapshot()
        result = self.receipt()
        result['findings'] = [{'id': 'F1', 'severity': 'BLOCKER', 'quote': '80%',
                               'reference': 'S1: no measured result', 'action': 'fix'}]
        result['decisions'] = [{'finding_id': 'F1', 'decision': 'accepted', 'rationale': 'Remove unsupported number'}]
        with self.assertRaises(ValueError):
            self.record(receipt=result)
        result['findings'][0]['severity'] = 'MAJOR'
        result['decisions'][0]['decision'] = 'rejected'
        with self.assertRaises(ValueError):
            self.record(receipt=result)
        result = self.receipt()
        result['questions'] = ['What did you implement?']
        with self.assertRaises(ValueError):
            self.record(receipt=result)

    def test_confirmed_experience_gap_can_remain_in_pass(self):
        self.start()
        self.snapshot()
        result = self.receipt()
        result['findings'] = [{'id': 'G1', 'severity': 'GAP', 'quote': 'Kafka required',
                               'reference': 'Q1: never used Kafka', 'action': 'retain_gap'}]
        result['decisions'] = [{'finding_id': 'G1', 'decision': 'retained_gap', 'rationale': 'Confirmed absent'}]
        self.assertEqual(self.record(receipt=result)['state'], 'passed')

    def test_result_validation_and_fresh_reviewer(self):
        self.start()
        self.snapshot()
        for change in ({'manifest_sha256': 'wrong'}, {'outcome': 'READY_TO_APPLY'},
                       {'questions': ['Question'] * 6}, {'reviewer_id': ''},
                       {'package_complete': 'true'}, {'outcome': 'needs_input', 'questions': []}):
            with self.subTest(change=change):
                result = self.receipt()
                result.update(change)
                with self.assertRaises(ValueError):
                    self.record(receipt=result)
        self.record('revise')
        self.snapshot()
        with self.assertRaises(ValueError):
            self.record(receipt=self.receipt(reviewer='agent-1-1'))

    def test_snapshot_damage_is_detected(self):
        self.start()
        self.snapshot()
        (self.app / 'review-cycles/001/rounds/001/cv.md').write_text('Tampered')
        self.assertFalse(self.status()['current'])
        with self.assertRaises(ValueError):
            self.record()

    def test_replaced_symlink_invalidates_live_cv(self):
        cv = self.app / 'cv.md'
        old_target = self.app / 'old-cv.md'
        cv.rename(old_target)
        cv.symlink_to(old_target)
        self.start()
        self.snapshot()
        cv.unlink()
        cv.write_text('Different live resume')
        self.assertFalse(self.status()['current'])
        with self.assertRaises(ValueError):
            self.record()

    def test_summary_write_failure_can_be_recovered_without_rewriting_result(self):
        self.start()
        self.snapshot()
        with patch.object(rc.os, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.record('needs_input')
        self.assertEqual(self.status()['state'], 'needs_input')
        result = self.app / 'review-cycles/001/rounds/001/result/result.json'
        original = result.read_bytes()
        rc.refresh_summary(self.app, root=self.root)
        self.assertEqual(original, result.read_bytes())
        self.assertIn('Describe your relevant experience.', (self.app / 'review.md').read_text())
        self.assertIn('result/report.md', (self.app / 'review.md').read_text())

    def test_failure_receipt_rejects_invalid_reviewer_and_complete_claim(self):
        self.start()
        self.snapshot()
        for change in ({'reviewer_id': {'name': 'reviewer'}}, {'package_complete': True}):
            result = self.receipt('review_unavailable')
            result.update(change)
            with self.assertRaises(ValueError):
                self.record(receipt=result)

    def test_manifest_change_after_review_invalidates(self):
        self.start()
        self.snapshot()
        self.record()
        manifest = self.app / 'review-cycles/001/rounds/001/manifest.json'
        manifest.write_text(manifest.read_text() + ' ')
        self.assertFalse(self.status()['current'])
        self.assertIn('manifest changed since review', self.status()['changes'])

    def test_cli_round_trip_and_stale_exit_code(self):
        script = self.root / 'scripts/review_cycle.py'
        script.parent.mkdir()
        script.write_bytes(Path(rc.__file__).read_bytes())
        def cli(*args):
            return subprocess.run([sys.executable, str(script), *map(str, args)],
                                  text=True, capture_output=True, cwd=self.root)
        self.assertEqual(cli('start', self.app).returncode, 0)
        capture = cli('snapshot', self.app, '--facts', self.facts, '--source', self.profile)
        self.assertEqual(capture.returncode, 0, capture.stderr)
        receipt = self.app / 'receipt.json'
        receipt.write_text(json.dumps(self.receipt()))
        recorded = cli('record', self.app, '--result', receipt)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.assertEqual(json.loads(recorded.stdout)['state'], 'passed')
        self.assertEqual(cli('status', self.app).returncode, 0)
        (self.app / 'review.md').unlink()
        self.assertEqual(cli('status', self.app, '--refresh-summary').returncode, 0)
        self.assertIn('result/report.md', (self.app / 'review.md').read_text())
        self.profile.write_text('Changed source')
        stale = cli('status', self.app)
        self.assertEqual(stale.returncode, 2)
        self.assertFalse(json.loads(stale.stdout)['current'])

    def test_no_legacy_review_overwrite_or_unrelated_folder(self):
        legacy = self.app / 'review.md'
        legacy.write_text('Existing private review')
        with self.assertRaises(ValueError):
            self.start()
        self.assertEqual(legacy.read_text(), 'Existing private review')
        self.assertFalse((self.app / 'review-cycles').exists())
        with self.assertRaises(ValueError):
            rc.start(self.root, root=self.root)

    def test_lock_and_failed_snapshot_are_recoverable(self):
        lock = self.app / '.review-cycle.lock'
        lock.write_text('')
        with self.assertRaises(ValueError):
            self.start()
        lock.unlink()
        self.start()
        self.facts.write_text('')
        with self.assertRaises(ValueError):
            self.snapshot()
        self.assertEqual(self.status()['round'], 0)
        self.assertFalse(lock.exists())
        self.facts.write_text('Facts')
        self.assertEqual(self.snapshot()['round'], 1)

    def test_interrupted_publication_does_not_consume_round(self):
        self.start()
        original = Path.write_bytes
        def fail_manifest(path, data):
            if path.name == 'manifest.json':
                raise OSError('simulated interrupted write')
            return original(path, data)
        with patch.object(Path, 'write_bytes', fail_manifest):
            with self.assertRaises(OSError):
                self.snapshot()
        self.assertEqual(self.status()['round'], 0)
        self.assertEqual(self.snapshot()['round'], 1)


if __name__ == '__main__':
    unittest.main()
