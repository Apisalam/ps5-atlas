import contextlib
import copy
from datetime import datetime, timezone, timedelta
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('build', Path(__file__).resolve().parents[1] / 'scripts/build.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)


def entry(version='1.0', **fields):
    return {'title': 'Test Homebrew', 'title_id': 'PPSA12345', 'version': version,
            'region': 'EUR', 'format': 'exfat',
            'files': [{'url': f'https://example.org/{version}.zip'}], **fields}


def source(sid='one', **fields):
    return {'id': sid, 'name': sid, 'adapter': 'native', 'url': f'https://example.org/{sid}.json',
            'enabled': True, 'authorization': {'status': 'approved', 'basis': 'Fixture owner permission',
                                             'evidence_url': 'https://example.org/license'}, **fields}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / 'config.json'

    def run_build(self, sources, payloads, day=0):
        self.config.write_text(json.dumps({'sources': sources, 'catalog_url': 'https://example.org/catalog.json'}))
        def fetcher(url):
            value = payloads[url] if isinstance(payloads, dict) and 'entries' not in payloads and 'packages' not in payloads else payloads
            if isinstance(value, Exception):
                raise value
            return copy.deepcopy(value)
        with contextlib.redirect_stdout(io.StringIO()):
            return b.build(self.config, self.root, fetcher, NOW + timedelta(days=day))

    def read(self, file):
        return json.loads((self.root / file).read_text())

    def test_preserves_versions_regions_formats_and_mirrors(self):
        records = [entry('1.9'), entry('1.10'), entry('1.10', region='USA'),
                   entry('1.10', format='ffpkg'), entry('1.10', files=[{'url': 'https://mirror.example/1.10.zip'}])]
        self.assertEqual(self.run_build([source()], {'entries': records + [records[0]]}), 0)
        self.assertEqual(len(self.read('catalog.json')['entries']), 5)
        latest = {r['version']: r['latest_in_variant'] for r in self.read('releases.json')['entries'] if r['region'] == 'EUR' and r['format'] == 'exfat'}
        self.assertEqual(latest, {'1.9': False, '1.10': True})

    def test_historical_versions_survive_refresh_and_order_is_stable(self):
        self.run_build([source()], {'entries': [entry('1.0')]})
        self.run_build([source()], {'entries': [entry('2.0')]}, day=1)
        self.assertEqual(len(self.read('catalog.json')['entries']), 2)
        self.assertEqual({r['status'] for r in self.read('releases.json')['entries']}, {'current', 'historical'})
        before = (self.root / 'catalog.json').read_bytes()
        self.run_build([source()], {'entries': [entry('2.0')]}, day=2)
        self.assertEqual((self.root / 'catalog.json').read_bytes(), before)

    def test_removed_app_and_replaced_mirror_not_published_but_history_kept(self):
        self.run_build([source()], {'entries': [entry(), entry(title_id='PPSA99998', title='Other')]})
        changed = entry(files=[{'url': 'https://mirror.example/new.zip'}])
        self.run_build([source()], {'entries': [changed]}, day=1)
        self.assertEqual(len(self.read('catalog.json')['entries']), 1)
        self.assertEqual(len(self.read('catalog-state.json')['sources']['one']['history']), 3)

    def test_partial_failure_keeps_cached_source_and_marks_stale(self):
        sources = [source(), source('two')]
        self.run_build(sources, {sources[0]['url']: {'entries': [entry()]}, sources[1]['url']: {'entries': [entry('2')]}})
        self.run_build(sources, {sources[0]['url']: OSError('offline'), sources[1]['url']: {'entries': [entry('2')]}}, day=1)
        self.assertEqual(len(self.read('catalog.json')['entries']), 2)
        self.assertEqual(self.read('build-report.json')['status'], 'degraded')
        self.assertTrue(any(r['stale'] for r in self.read('releases.json')['entries']))

    def test_all_fail_reports_and_preserves_every_previous_output(self):
        self.run_build([source()], {'entries': [entry()]})
        paths = ['catalog.json', 'catalog-state.json', 'releases.json', 'sources.json']
        before = {p: (self.root / p).read_bytes() for p in paths}
        self.assertEqual(self.run_build([source()], OSError('offline')), 1)
        self.assertEqual(self.read('build-report.json')['status'], 'error')
        self.assertEqual({p: (self.root / p).read_bytes() for p in paths}, before)

    def test_empty_or_partially_invalid_source_is_rejected_transactionally(self):
        for payload in [{'entries': []}, {'entries': [entry(), {'title': 'broken'}]}, {'packages': []}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.run_build([source()], payload), 1)
                self.assertFalse((self.root / 'catalog.json').exists())

    def test_authorization_required_and_config_change_invalidates_cache(self):
        self.assertEqual(self.run_build([source(authorization={})], {'entries': [entry()]}), 1)
        self.run_build([source()], {'entries': [entry()]})
        before = (self.root / 'catalog.json').read_bytes()
        self.assertEqual(self.run_build([source(url='https://other.example/feed')], OSError('offline')), 1)
        self.assertEqual((self.root / 'catalog.json').read_bytes(), before)

    def test_disabled_source_is_not_fetched_or_retained(self):
        first, second = source(), source('two')
        self.run_build([first, second], {first['url']: {'entries': [entry()]}, second['url']: {'entries': [entry('2')]}})
        first['enabled'] = False
        self.run_build([first, second], {second['url']: {'entries': [entry('2')]}})
        self.assertEqual(len(self.read('catalog.json')['entries']), 1)
        self.assertNotIn('one', self.read('catalog-state.json')['sources'])

    def test_cache_expires_after_seven_days(self):
        sources = [source(), source('two')]
        self.run_build(sources, {sources[0]['url']: {'entries': [entry()]}, sources[1]['url']: {'entries': [entry('2')]}})
        self.run_build(sources, {sources[0]['url']: OSError('offline'), sources[1]['url']: {'entries': [entry('2')]}}, day=8)
        self.assertEqual(len(self.read('catalog.json')['entries']), 1)

    def test_unknown_version_order_not_guessed_and_shared_ids_separate(self):
        self.assertLess(b.version_key('1.9'), b.version_key('1.10'))
        self.assertEqual(b.version_key('v01.002.000'), b.version_key('1.2'))
        self.assertIsNone(b.version_key('nightly-abc'))
        self.assertNotEqual(b.group_identity(entry(atlas={'repository': 'https://github.com/a/a'})),
                            b.group_identity(entry(atlas={'repository': 'https://github.com/b/b'})))

    def test_pegasus_both_shapes_keep_metadata_and_mirrors(self):
        package = {'title': 'Homebrew (v1.2)', 'titleId': 'PPSA12345', 'version': '1.2', 'region': 'EUR',
                   'downloadLinks': [{'name': 'Dump - One', 'url': 'https://one.example/game.zip'},
                                     {'name': 'Dump - Two', 'url': 'https://two.example/game.zip'}]}
        rows, _ = b.pegasus({'packages': [package]}, {})
        b.validate_entry(rows[0])
        self.assertEqual(rows[0]['atlas']['original_package'], package)
        self.assertEqual(len(rows[0]['source_sets']), 2)
        rows, _ = b.pegasus({'packages': [{'title': 'Another', 'url': 'https://one.example/game.pkg', 'filename': 'game.pkg'}]}, {})
        self.assertEqual(rows[0]['files'][0]['name'], 'game.pkg')

    def test_homebrew_allowlist_filters_reservations_and_preserves_hash(self):
        app = {'titleid': 'PPSA12345', 'name': 'Homebrew', 'version': '1.0', 'license': 'MIT',
               'source_repo': 'https://github.com/author/app',
               'artifact_url': 'https://github.com/author/app/releases/download/v1.0/app.zip',
               'sha256': 'a'*64, 'format': 'zip', 'kind': 'app'}
        rows, skipped = b.homebrew({'apps': [app, {**app, 'source_repo': 'https://github.com/unreviewed/app'},
                                           {**app, 'artifact_url': None}]}, {'allow_repositories': [app['source_repo']]})
        self.assertEqual(skipped, 2)
        b.validate_entry(rows[0])
        self.assertNotIn('format', rows[0])
        self.assertEqual(rows[0]['files'][0]['sha256'], 'a'*64)
        with self.assertRaises(ValueError):
            b.homebrew({'apps': [{**app, 'artifact_url': 'https://mirror.example/app.zip'}]}, {'allow_repositories': [app['source_repo']]})

    def test_pegasus_multipart_links_are_one_ordered_download(self):
        package = {'title': 'Multipart Homebrew', 'downloadLinks': [
            {'name': 'Dump - Mirror part 2', 'url': 'https://one.example/app.7z.002'},
            {'name': 'Dump - Mirror part 1', 'url': 'https://one.example/app.7z.001'},
            {'name': 'Other mirror', 'url': 'https://two.example/app.zip'}]}
        rows, _ = b.pegasus({'packages': [package]}, {})
        self.assertEqual(len(rows[0]['source_sets']), 2)
        self.assertEqual([f['url'] for f in rows[0]['files']],
                         ['https://one.example/app.7z.001', 'https://one.example/app.7z.002'])
        package['downloadLinks'].pop(1)
        with self.assertRaises(ValueError):
            b.pegasus({'packages': [package]}, {})

    def test_opaque_pegasus_edition_fields_are_not_deduplicated(self):
        package = {'title': 'Homebrew', 'url': 'https://example.org/game.zip', 'filename': 'game.zip'}
        rows, _ = b.pegasus({'packages': [{**package, 'edition': 'Original'},
                                        {**package, 'edition': 'Revised'}]}, {})
        self.assertNotEqual(b.entry_identity(rows[0]), b.entry_identity(rows[1]))

    def test_catalog_is_independent_of_upstream_order(self):
        records = [entry('1'), entry('2'), entry('3', region='USA')]
        self.assertEqual(self.run_build([source()], {'entries': records}), 0)
        before = (self.root / 'catalog.json').read_bytes()
        self.assertEqual(self.run_build([source()], {'entries': list(reversed(records))}), 0)
        self.assertEqual((self.root / 'catalog.json').read_bytes(), before)

    def test_transport_size_limit_and_retry(self):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, n):
                return b'{"entries": []}'
        opener = unittest.mock.Mock()
        opener.open.side_effect = [b.HTTPError('https://example.org/a', 503, 'offline', {}, None), Response()]
        with patch.object(b, 'public_endpoint'), patch.object(b, 'build_opener', return_value=opener), patch.object(b.time, 'sleep'):
            self.assertEqual(b.fetch('https://example.org/a'), {'entries': []})
            self.assertEqual(opener.open.call_count, 2)
        opener.open.side_effect = None
        opener.open.return_value = Response()
        with patch.object(b, 'public_endpoint'), patch.object(b, 'build_opener', return_value=opener), patch.object(b, 'MAX_BYTES', 2):
            with self.assertRaises(ValueError):
                b.fetch('https://example.org/a')

    def test_github_releases_pagination_filters_and_all_versions(self):
        template = {'tag_name': 'v1.0', 'prerelease': False, 'assets': [
            {'name': 'PPSA12345.zip', 'browser_download_url': 'https://github.com/author/app/releases/download/v1.0/PPSA12345.zip',
             'digest': 'sha256:' + 'b'*64, 'size': 123}, {'name': 'source.zip'}]}
        calls = []
        def fetcher(url):
            calls.append(url)
            return [template]*100 if 'page=1' in url.split('per_page=100&')[1] else [{**template, 'tag_name': 'v2.0'}]
        src = {'repository': 'author/app', 'title': 'App', 'title_id': 'PPSA12345', 'license': 'MIT', 'asset_pattern': 'PPSA12345.zip'}
        rows, _ = b.github_releases(src, fetcher)
        self.assertEqual(len(calls), 2)
        self.assertEqual({r['version'] for r in rows}, {'1.0', '2.0'})
        self.assertEqual(b.github_releases(src, lambda _: [{**template, 'draft': True}])[0], [])
        self.assertEqual(b.github_releases(src, lambda _: [{**template, 'prerelease': True}])[0], [])
        bad = copy.deepcopy(template)
        del bad['assets'][0]['digest']
        with self.assertRaises(ValueError):
            b.github_releases(src, lambda _: [bad])

    def test_public_https_only_including_redirects_and_dns(self):
        for url in ['http://example.org/a', 'https://127.0.0.1/a', 'https://192.168.1.4/a',
                    'https://localhost/a', 'https://ps5.local/a', 'https://user:password@example.org/a']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                b.https_url(url)
        with patch.object(b, 'getproxies', return_value={}), patch.object(b.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('192.168.1.4', 443))]):
            with self.assertRaises(ValueError):
                b.public_endpoint('https://console.example/a')
            with self.assertRaises(ValueError):
                b.PublicRedirects().redirect_request(None, None, 302, '', {}, 'https://console.example/a')

    def test_duplicate_source_ids_and_native_file_hash_validation(self):
        self.assertEqual(self.run_build([source(), source()], {'entries': [entry()]}), 1)
        with self.assertRaises(ValueError):
            b.validate_entry(entry(files=[{'url': 'https://example.org/a', 'sha256': 'bad'}]))
        with self.assertRaises(ValueError):
            b.validate_entry(entry(source_sets=[{'host': 'bad', 'files': []}]))


if __name__ == '__main__':
    unittest.main()
