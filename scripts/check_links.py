#!/usr/bin/env python3
"""Check listed GitHub assets against publisher metadata; do not download binaries."""
import argparse
from pathlib import Path
from urllib.parse import unquote, quote, urlsplit
from build import ROOT, fetch, read_json


def check(root, fetcher=fetch):
    catalog = read_json(root / 'catalog.json')
    cache = {}
    checked = set()
    for entry in catalog['entries']:
        for file in entry['files']:
            url = file['url']
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
            if asset.get('digest') != 'sha256:' + file.get('sha256', ''):
                raise ValueError(f'Publisher digest mismatch for {entry["title"]}')
            checked.add(url)
    print(f'Verified {len(checked)} release assets against live publisher metadata; no binaries downloaded')
    return len(checked)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    check(parser.parse_args().root)
