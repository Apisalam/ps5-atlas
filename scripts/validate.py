#!/usr/bin/env python3
"""Offline contract check against PS5 Library's documented native entries format."""
import argparse
from pathlib import Path
from build import ROOT, digest, read_json, validate_config, validate_entry


def validate(root):
    config = read_json(root / 'atlas-sources.json')
    validate_config(config)
    catalog = read_json(root / 'catalog.json')
    assert isinstance(catalog, dict), 'catalog.json missing'
    entries = catalog.get('entries')
    assert isinstance(entries, list) and entries, 'Native catalog must contain entries'
    ids = set()
    for entry in entries:
        validate_entry(entry)
        assert entry['id'] not in ids, 'Duplicate entry ID'
        ids.add(entry['id'])
    assert catalog['version'] == digest(entries), 'Catalog content digest does not match'
    index = read_json(root / 'releases.json')
    assert {e['id'] for e in index['entries']} == ids, 'Release index/catalog mismatch'
    sources = read_json(root / 'sources.json')
    assert sources == {'sources': [{'name': 'PS5 Atlas', 'url': config['catalog_url'], 'enabled': True}]}, 'Client source list differs from generated catalog endpoint'
    state = read_json(root / 'catalog-state.json')
    approved = {s['id'] for s in config['sources'] if s.get('enabled', True)}
    assert set(state['sources']) <= approved, 'State includes disabled or removed source'
    for cached in state['sources'].values():
        for entry in cached['history'].values():
            validate_entry(entry)
    print(f'Validated {len(entries)} entries, unique IDs, checksums, source policy and matching release index')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    validate(parser.parse_args().root)
