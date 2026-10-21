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
        self.catalog = {'entries': [{'id': 'app', 'title': 'App', 'files': [{'url': self.url, 'sha256': 'a'*64}]}]}
        self.index = {'entries': [{'id': 'app', 'stale': False, 'status': 'current'}]}
        self.asset = {'browser_download_url': self.url, 'state': 'uploaded', 'digest': 'sha256:'+'a'*64}

    def run_check(self, release):
        (self.root / 'catalog.json').write_text(json.dumps(self.catalog))
        (self.root / 'releases.json').write_text(json.dumps(self.index))
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

    def test_alternative_mirrors_are_verified_and_duplicate_primary_is_cached(self):
        primary = self.catalog['entries'][0]['files']
        self.catalog['entries'][0]['source_sets'] = [
            {'host': 'primary', 'files': primary},
            {'host': 'mirror', 'files': [{'url': self.url.replace('app.zip', 'other.zip'), 'sha256': 'b'*64}]}]
        with self.assertRaisesRegex(ValueError, 'Missing published asset'):
            self.run_check({'assets': [self.asset]})

    def test_stale_and_historical_entries_are_not_probed(self):
        for row in [{'id': 'app', 'stale': True, 'status': 'current'},
                    {'id': 'app', 'stale': False, 'status': 'historical'}]:
            self.index['entries'] = [row]
            def fail(_):
                self.fail('Cached/historical metadata must not be probed')
            (self.root / 'catalog.json').write_text(json.dumps(self.catalog))
            (self.root / 'releases.json').write_text(json.dumps(self.index))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(check(self.root, fail), 0)

    def test_uppercase_hex_digest_is_equivalent(self):
        self.catalog['entries'][0]['files'][0]['sha256'] = 'A'*64
        self.assertEqual(self.run_check({'assets': [self.asset]}), 1)
