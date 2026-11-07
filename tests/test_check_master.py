import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import check_master


class MasterCheckTests(unittest.TestCase):
    def test_malformed_fingerprint_cannot_be_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.md'
            source.write_text('unchanged')
            resume = root / 'resume.md'
            good = hashlib.sha256(b'unchanged').hexdigest()
            resume.write_text(f'- `source.md` `{good}`\n- `other.md` `{"0" * 63}`\n')
            with patch.object(check_master, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'Malformed source fingerprint'):
                    check_master.check(resume)

    def test_valid_fingerprint_detects_changed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.md'
            source.write_text('changed')
            resume = root / 'resume.md'
            resume.write_text(f'- `source.md` `{hashlib.sha256(b"original").hexdigest()}`\n')
            with patch.object(check_master, 'ROOT', root):
                self.assertEqual(check_master.check(resume), ['source.md'])


if __name__ == '__main__':
    unittest.main()
