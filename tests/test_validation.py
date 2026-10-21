import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build import build, digest
from validate import validate
from test_build import entry, source, NOW


class ContractValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        config = {'sources': [source()], 'catalog_url': 'https://example.org/catalog.json'}
        (self.root / 'atlas-sources.json').write_text(json.dumps(config))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(build(self.root / 'atlas-sources.json', self.root,
                                   lambda _: {'entries': [entry()]}, NOW), 0)
        self.baseline = {p.name: json.loads(p.read_text()) for p in self.root.glob('*.json')}

    def verify(self, overrides=None):
        data = {**copy.deepcopy(self.baseline), **(overrides or {})}
        for name, value in data.items():
            (self.root / name).write_text(json.dumps(value))
        with contextlib.redirect_stdout(io.StringIO()):
            validate(self.root)

    def test_complete_generated_contract_passes(self):
        self.verify()

    def test_external_config_for_isolated_build(self):
        config = self.root / 'external-config.json'
        (self.root / 'atlas-sources.json').rename(config)
        with contextlib.redirect_stdout(io.StringIO()):
            validate(self.root, config)

    def test_native_upstream_id_is_preserved_in_state_and_replaced_in_catalog(self):
        path = self.root / 'atlas-sources.json'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(build(path, self.root,
                                   lambda _: {'entries': [entry(id='publisher-id')]}, NOW), 0)
            validate(self.root)
        state = json.loads((self.root / 'catalog-state.json').read_text())
        self.assertEqual(next(iter(state['sources']['one']['current'].values()))['id'], 'publisher-id')
        catalog = json.loads((self.root / 'catalog.json').read_text())
        self.assertTrue(catalog['entries'][0]['id'].startswith('atlas-'))

    def test_index_duplicates_and_false_provenance_are_rejected(self):
        for field, value in [('sources', ['unapproved']), ('stale', True),
                             ('latest_in_variant', False), ('status', 'historical'),
                             ('version', '9.0')]:
            index = copy.deepcopy(self.baseline['releases.json'])
            index['entries'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify({'releases.json': index})
        index = copy.deepcopy(self.baseline['releases.json'])
        index['entries'].append(index['entries'][0])
        with self.assertRaisesRegex(ValueError, 'index/catalog'):
            self.verify({'releases.json': index})

    def test_content_tampering_with_recomputed_digest_is_rejected(self):
        catalog = copy.deepcopy(self.baseline['catalog.json'])
        catalog['entries'][0]['files'][0]['url'] = 'https://other.example/game.zip'
        catalog['version'] = digest(catalog['entries'])
        with self.assertRaisesRegex(ValueError, 'content ID'):
            self.verify({'catalog.json': catalog})

    def test_source_snapshot_and_configuration_tampering_are_rejected(self):
        state = copy.deepcopy(self.baseline['catalog-state.json'])
        state['sources']['one']['fingerprint'] = 'bad'
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            self.verify({'catalog-state.json': state})
        state = copy.deepcopy(self.baseline['catalog-state.json'])
        state['sources']['one']['active'] = {}
        with self.assertRaisesRegex(ValueError, 'not active'):
            self.verify({'catalog-state.json': state})

    def test_expired_source_can_stay_in_history_without_being_published(self):
        # A real two-source build must validate after one cached source expires.
        first, second = source(), source('two')
        config = {'sources': [first, second], 'catalog_url': 'https://example.org/catalog.json'}
        path = self.root / 'atlas-sources.json'
        path.write_text(json.dumps(config))
        from datetime import timedelta
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(build(path, self.root, lambda _: {'entries': [entry()]}, NOW), 0)
            def fetcher(url):
                if url == first['url']:
                    raise OSError('offline')
                return {'entries': [entry('2')]}
            self.assertEqual(build(path, self.root, fetcher, NOW + timedelta(days=8)), 0)
            validate(self.root)


if __name__ == '__main__':
    unittest.main()
