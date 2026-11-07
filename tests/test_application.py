import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.application import canonical_url, initialize


class ApplicationsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_different_roles_and_repeat(self):
        a = initialize(self.root, 'Example', 'Backend', 'https://jobs.example/1?utm_source=x')
        b = initialize(self.root, 'Example', 'SRE', 'https://jobs.example/2')
        self.assertNotEqual(a, b)
        self.assertEqual(a, initialize(self.root, 'Example Inc', 'Renamed', 'https://jobs.example/1'))
        self.assertIn('INBOX', (a / 'status.md').read_text())
        self.assertIn('unknown', (a / 'job.md').read_text())

    def test_add_source_identity_without_duplicate(self):
        a = initialize(self.root, 'Example', 'Engineer', 'https://jobs.example/1')
        self.assertEqual(a, initialize(self.root, 'Example', 'Engineer', 'https://jobs.example/1', 'board:123'))
        self.assertEqual(a, initialize(self.root, 'Example', 'Engineer', source_id='board:123'))

    def test_conflicting_identity_stops(self):
        initialize(self.root, 'Example', 'Engineer', 'https://jobs.example/1', 'board:123')
        with self.assertRaises(ValueError):
            initialize(self.root, 'Example', 'Engineer', 'https://jobs.example/2', 'board:123')

    def test_route_fragments_keep_distinct_jobs(self):
        first = initialize(self.root, 'Example', 'Backend', 'https://jobs.example/#/jobs/1')
        second = initialize(self.root, 'Example', 'SRE', 'https://jobs.example/#/jobs/2')
        self.assertNotEqual(first, second)
        self.assertEqual(canonical_url('https://jobs.example/#/jobs/1'), 'https://jobs.example/#/jobs/1')

    def test_failed_identity_update_preserves_existing_metadata(self):
        app = initialize(self.root, 'Example', 'Backend', 'https://jobs.example/1')
        identity = (app / 'identity.json').read_bytes()
        with patch('scripts.application.os.replace', side_effect=OSError('simulated interruption')):
            with self.assertRaises(OSError):
                initialize(self.root, 'Example', 'Backend', 'https://jobs.example/1', 'board:1')
        self.assertEqual((app / 'identity.json').read_bytes(), identity)
        initialize(self.root, 'Other', 'Role', 'https://other.example/1')

    def test_no_identity_and_bad_url(self):
        with self.assertRaises(ValueError):
            initialize(self.root, 'Example', 'Engineer')
        with self.assertRaises(ValueError):
            canonical_url('file:///private')
        self.assertEqual(canonical_url('HTTPS://Example.com:443/a/?utm_x=1&x=2#frag'), 'https://example.com/a?x=2')
        for url in ('https://[::1]/job', 'https://[::1]:8443/job', 'https://[::1]:443/job'):
            self.assertEqual(canonical_url(canonical_url(url)), canonical_url(url))
        self.assertEqual(canonical_url('https://[::1]/job'), 'https://[::1]/job')
        self.assertEqual(canonical_url('https://[::1]:8443/job'), 'https://[::1]:8443/job')


if __name__ == '__main__':
    unittest.main()
