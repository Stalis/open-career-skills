import tempfile
import unittest
from pathlib import Path
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

    def test_no_identity_and_bad_url(self):
        with self.assertRaises(ValueError):
            initialize(self.root, 'Example', 'Engineer')
        with self.assertRaises(ValueError):
            canonical_url('file:///private')
        self.assertEqual(canonical_url('HTTPS://Example.com:443/a/?utm_x=1&x=2#frag'), 'https://example.com/a?x=2')


if __name__ == '__main__':
    unittest.main()
