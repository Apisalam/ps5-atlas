import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_links import check


class PublisherVerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.url = 'https://github.com/author/app/releases/download/v1.0/app.zip'
        self.catalog = {'entries': [{'title': 'App', 'files': [{'url': self.url, 'sha256': 'a'*64}]}]}
        self.asset = {'browser_download_url': self.url, 'state': 'uploaded', 'digest': 'sha256:'+'a'*64}

    def run_check(self, release):
        (self.root / 'catalog.json').write_text(json.dumps(self.catalog))
        with contextlib.redirect_stdout(io.StringIO()):
            return check(self.root, lambda _: release)

    def test_published_asset_and_digest_match(self):
        self.assertEqual(self.run_check({'assets': [self.asset]}), 1)

    def test_changed_digest_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            self.run_check({'assets': [{**self.asset, 'digest': 'sha256:'+'b'*64}]})

    def test_removed_asset_or_draft_is_rejected(self):
        for release in [{'assets': []}, {'draft': True, 'assets': [self.asset]}]:
            with self.subTest(release=release), self.assertRaises(ValueError):
                self.run_check(release)

    def test_unsupported_host_is_not_probed(self):
        self.catalog['entries'][0]['files'][0]['url'] = 'https://other.example/app.zip'
        with self.assertRaisesRegex(ValueError, 'pinned GitHub'):
            self.run_check({'assets': []})
