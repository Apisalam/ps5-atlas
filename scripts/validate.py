#!/usr/bin/env python3
"""Offline PS5 Library contract, identity and publication provenance validation."""
import argparse
from pathlib import Path
from build import (ROOT, digest, entry_identity, group_identity, read_json,
                   validate_config, validate_entry, version_key)


def require(condition, message):
    # Do not use assert: these checks must also run under python -O.
    if not condition:
        raise ValueError(message)


def validate(root, config_path=None):
    config = read_json(config_path or root / 'atlas-sources.json')
    validate_config(config)
    catalog = read_json(root / 'catalog.json')
    require(isinstance(catalog, dict), 'catalog.json missing')
    entries = catalog.get('entries')
    require(isinstance(entries, list) and entries, 'Native catalog must contain entries')
    ids = set()
    maxima = {}
    for entry in entries:
        validate_entry(entry)
        require(entry.get('id') == 'atlas-' + entry_identity(entry), 'Entry content ID does not match')
        require(entry['id'] not in ids, 'Duplicate entry ID')
        ids.add(entry['id'])
        key = version_key(entry.get('version'))
        if key is not None:
            group = group_identity(entry)
            maxima[group] = max(maxima.get(group, key), key)
    require(catalog['version'] == digest(entries), 'Catalog content digest does not match')
    index = read_json(root / 'releases.json')['entries']
    require(len(index) == len(ids) and {e['id'] for e in index} == ids, 'Release index/catalog mismatch')
    sources = read_json(root / 'sources.json')
    require(sources == {'sources': [{'name': 'PS5 Atlas', 'url': config['catalog_url'], 'enabled': True}]},
            'Client source list differs from generated catalog endpoint')
    state = read_json(root / 'catalog-state.json')
    approved = {s['id']: s for s in config['sources'] if s.get('enabled', True)}
    require(set(state['sources']) <= approved.keys(), 'State includes disabled or removed source')
    report = read_json(root / 'build-report.json')
    require(report['status'] in ('ok', 'degraded'), 'Build did not succeed')
    require(report['catalog_version'] == catalog['version'] and report['records'] == len(entries),
            'Build report/catalog mismatch')
    statuses = {s['id']: s['status'] for s in report['sources']}
    expected = {}
    for sid, cached in state['sources'].items():
        require(cached['fingerprint'] == digest(approved[sid]), 'Source configuration fingerprint mismatch')
        for key, entry in cached['history'].items():
            validate_entry(entry)
            require(key == entry_identity(entry), 'History identity mismatch')
        for bucket in ('current', 'active'):
            require(all(cached['history'].get(k) == e for k, e in cached[bucket].items()),
                    'Source snapshot is not in history')
        require(cached['current'].keys() <= cached['active'].keys(), 'Current snapshot is not active')
        if statuses.get(sid) not in ('ok', 'stale'):
            continue
        for key, entry in cached['active'].items():
            record = expected.setdefault('atlas-' + key, {'entry': entry, 'sources': [],
                                                         'current': False, 'stale': True})
            record['sources'].append(sid)
            record['current'] |= key in cached['current']
            record['stale'] &= statuses[sid] == 'stale'
    require(set(expected) == ids, 'Catalog differs from approved active snapshots')
    by_id = {e['id']: e for e in entries}
    for row in index:
        entry = by_id[row['id']]
        record = expected[row['id']]
        require({k: v for k, v in entry.items() if k != 'id'} ==
                {k: v for k, v in record['entry'].items() if k != 'id'},
                'Catalog entry differs from source snapshot')
        for field in ('title', 'title_id', 'version', 'region', 'format'):
            require(row.get(field) == entry.get(field), f'Release index {field} mismatch')
        require(row['sources'] == sorted(record['sources']) and row['stale'] == record['stale']
                and row['status'] == ('current' if record['current'] else 'historical'),
                'Release index provenance mismatch')
        version = version_key(entry.get('version'))
        latest = None if version is None else version == maxima[group_identity(entry)]
        require(row['latest_in_variant'] is latest, 'Release index latest version mismatch')
    print(f'Validated {len(entries)} entries, content IDs, checksums, approved snapshots and release index')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--config', type=Path, help='Source config used for an isolated build')
    args = parser.parse_args()
    validate(args.root, args.config)
