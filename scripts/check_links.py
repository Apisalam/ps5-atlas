#!/usr/bin/env python3
"""Check listed GitHub assets against publisher metadata; do not download binaries."""
import argparse
from pathlib import Path
from urllib.parse import unquote, quote, urlsplit
from build import ROOT, fetch, read_json, https_url


def check(root, fetcher=fetch):
    catalog = read_json(root / 'catalog.json')
    index = read_json(root / 'releases.json')
    rows = {r['id']: r for r in index['entries']}
    cache = {}
    checked = set()
    skipped = 0
    for entry in catalog['entries']:
        row = rows[entry['id']]
        # Retained historical versions and stale snapshots are explicitly unverified.
        # Probing them would turn an upstream outage into a publication outage.
        if row['stale'] or row['status'] == 'historical':
            skipped += 1
            continue
        files = entry['files'] + [f for mirror in entry.get('source_sets', []) for f in mirror['files']]
        for file in files:
            url = file['url']
            https_url(url)
            checksum = file.get('sha256', '').lower()
            if (url, checksum) in checked:
                continue
            parts = urlsplit(url).path.strip('/').split('/')
            if urlsplit(url).hostname != 'github.com' or len(parts) != 6 or parts[2:4] != ['releases', 'download']:
                raise ValueError('Live verification currently supports pinned GitHub release assets only')
            owner, repo, _, _, tag, _ = parts
            api = f'https://api.github.com/repos/{owner}/{repo}/releases/tags/{quote(unquote(tag), safe="")}'
            if api not in cache:
                cache[api] = fetcher(api)
            release = cache[api]
            if release.get('draft'):
                raise ValueError('Draft release is not publicly available')
            asset = next((a for a in release.get('assets', []) if a.get('browser_download_url') == url), None)
            if not asset or asset.get('state') != 'uploaded':
                raise ValueError(f'Missing published asset for {entry["title"]}')
            if (asset.get('digest') or '').lower() != 'sha256:' + checksum:
                raise ValueError(f'Publisher digest mismatch for {entry["title"]}')
            checked.add((url, checksum))
    print(f'Verified {len(checked)} release assets against live publisher metadata; '
          f'skipped {skipped} stale/historical entries; no binaries downloaded')
    return len(checked)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    check(parser.parse_args().root)
