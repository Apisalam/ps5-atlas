#!/usr/bin/env python3
"""PS5 Atlas: read public metadata, never contact a console or fetch game binaries."""
import argparse
import copy
from datetime import datetime, timezone, timedelta
import fnmatch
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, unquote
from urllib.request import Request, build_opener, HTTPRedirectHandler, getproxies

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 35_000_000
MAX_RECORDS = 50_000


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def https_url(url):
    if not isinstance(url, str):
        raise ValueError('URL must be a string')
    p = urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Expected public HTTPS URL without credentials')
    host = p.hostname.lower()
    if host == 'localhost' or host.endswith(('.local', '.localhost', '.internal')) or '.' not in host:
        raise ValueError('Local hosts are not allowed')
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not addr.is_global:
            raise ValueError('Non-public IP addresses are not allowed')
    return url


def public_endpoint(url):
    https_url(url)
    # HTTPS proxies resolve the destination themselves (local DNS may be disabled).
    if getproxies().get('https'):
        return
    host = urlsplit(url).hostname
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Source resolves to a non-public address')


class PublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_endpoint(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    public_endpoint(url)
    request = Request(url, headers={'User-Agent': 'PS5-Atlas/1.0 (+https://github.com/Apisalam/ps5-atlas)',
                                    'Accept': 'application/json'})
    for attempt in range(3):
        try:
            with build_opener(PublicRedirects()).open(request, timeout=30) as response:
                data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError('Source exceeds 35 MB')
            return json.loads(data.decode('utf-8-sig'), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def write_json(path, value):
    """Replace one complete JSON document, never leave a truncated catalog."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                     dir=path.parent, delete=False) as handle:
        temp = Path(handle.name)
        handle.write(data)
    temp.replace(path)


def validate_entry(entry):
    if not isinstance(entry, dict) or not isinstance(entry.get('title'), str) or not entry['title'].strip():
        raise ValueError('Entry needs a title')
    files = entry.get('files')
    if not isinstance(files, list) or not files:
        raise ValueError('Entry needs non-empty files')
    for file in files:
        if not isinstance(file, dict):
            raise ValueError('Invalid file')
        https_url(file.get('url'))
        if 'sha256' in file and (not isinstance(file['sha256'], str)
                                 or not re.fullmatch(r'[0-9a-fA-F]{64}', file['sha256'])):
            raise ValueError('Invalid SHA-256')
        if 'name' in file and not isinstance(file['name'], str):
            raise ValueError('File name must be a string')
    mirrors = entry.get('source_sets', [])
    if not isinstance(mirrors, list) or any(not isinstance(m, dict) for m in mirrors):
        raise ValueError('source_sets must be an array of mirror objects')
    for mirror in mirrors:
        validate_entry({'title': entry['title'], 'files': mirror.get('files')})
    if mirrors and files != mirrors[0]['files']:
        raise ValueError('Primary files must match the first source set')
    if not isinstance(entry.get('atlas', {}), dict):
        raise ValueError('atlas provenance must be an object')
    for field in ('version', 'title_id', 'region', 'format', 'platform', 'kind',
                  'firmware', 'description', 'cover', 'password', 'size'):
        if field in entry and not isinstance(entry[field], str):
            raise ValueError(f'{field} must be a string')
    for field, allowed in (('platform', ('ps4', 'ps5')), ('kind', ('game', 'update', 'dlc')),
                           ('format', ('exfat', 'ffpkg', 'ffpfs', 'ffpfsc', 'fpkg', 'pkg'))):
        if field in entry and entry[field] not in allowed:
            raise ValueError(f'Unsupported native {field}')
    digest(entry)
    return entry


def homebrew(payload, source):
    if not isinstance(payload, dict) or not isinstance(payload.get('apps'), list):
        raise ValueError('Expected homebrew apps array')
    allowed = source.get('allow_repositories', [])
    result = []
    skipped = 0
    for app in payload['apps']:
        if not isinstance(app, dict):
            raise ValueError('Invalid app record')
        if app.get('source_repo') not in allowed or not app.get('artifact_url'):
            skipped += 1
            continue
        repo = app['source_repo']
        artifact = app['artifact_url']
        if not artifact.startswith(repo + '/releases/download/') or not app.get('license') or app['license'] == 'Unlicensed':
            raise ValueError('App lacks pinned developer release or license')
        entry = {'title': app['name'], 'title_id': app['titleid'], 'version': app['version'],
                 'platform': 'ps5', 'kind': 'game',
                 'files': [{'url': artifact, 'name': unquote(urlsplit(artifact).path.rsplit('/', 1)[-1]),
                            'sha256': app['sha256']}],
                 'description': app.get('description', ''), 'cover': app.get('icon') or app.get('icon_url') or '',
                 'atlas': {'repository': repo, 'license': app['license'], 'author': app.get('author'),
                           'content_kind': app.get('kind'), 'upstream_format': app.get('format'),
                           'upstream_updated': app.get('updated')}}
        # ZIP is a transport container, not an exFAT/FFPKG image format.
        if app.get('format') in ('ffpkg', 'ffpfs', 'ffpfsc', 'exfat', 'pkg', 'fpkg'):
            entry['format'] = app['format']
        for field in ('region', 'firmware'):
            if field in app:
                entry[field] = app[field]
        result.append(entry)
    return result, skipped


def pegasus(payload, source):
    if not isinstance(payload, dict) or not isinstance(payload.get('packages'), list):
        raise ValueError('Expected Pegasus packages array')
    result = []
    for package in payload['packages']:
        if not isinstance(package, dict):
            raise ValueError('Invalid package record')
        links = package.get('downloadLinks')
        if links is None:
            links = [{'url': package.get('url'), 'name': package.get('filename', '')}]
        if not isinstance(links, list) or not links:
            raise ValueError('Package has no links')
        mirrors = []
        multipart = {}
        for link in links:
            if not isinstance(link, dict):
                raise ValueError('Invalid Pegasus link')
            file = {'url': link.get('url')}
            if 'sha256' in link:
                file['sha256'] = link['sha256']
            elif len(links) == 1 and 'sha256' in package:
                file['sha256'] = package['sha256']
            # Pegasus name is the source label, not necessarily a filename.
            if package.get('filename') and len(links) == 1:
                file['name'] = package['filename']
            label = link.get('name') or urlsplit(file['url'] or '').hostname or ''
            filename = unquote(urlsplit(file['url'] or '').path.rsplit('/', 1)[-1])
            label_part = re.search(r'\bpart[\s._-]*(\d+)\b', label, re.I)
            file_part = re.search(r'(?:\.part(\d+)\.rar|\.(?:7z|zip)\.(\d+))$', filename, re.I)
            if label_part or file_part:
                number = int(label_part.group(1) if label_part else next(g for g in file_part.groups() if g))
                base_label = re.sub(r'\s*\bpart[\s._-]*\d+\b', '', label, flags=re.I).strip()
                base_file = re.sub(r'(?:\.part\d+\.rar|\.(?:7z|zip)\.\d+)$', '', filename, flags=re.I) if file_part else ''
                group = (urlsplit(file['url'] or '').hostname, base_label, base_file)
                if group not in multipart:
                    mirror = {'host': base_label, 'files': []}
                    multipart[group] = (mirror, [])
                    mirrors.append(mirror)
                multipart[group][1].append((number, file))
            else:
                mirrors.append({'host': label, 'files': [file]})
        for mirror, parts in multipart.values():
            parts.sort(key=lambda p: p[0])
            if [p[0] for p in parts] != list(range(1, len(parts) + 1)):
                raise ValueError('Multipart download has missing or duplicate parts')
            mirror['files'] = [p[1] for p in parts]
        entry = {'title': package.get('title') or package.get('name') or package.get('filename'),
                 'files': mirrors[0]['files'], 'source_sets': mirrors,
                 'atlas': {'original_package': package}}
        for a, b in [('titleId', 'title_id'), ('version', 'version'), ('region', 'region'),
                     ('format', 'format'), ('platform', 'platform'), ('firmware', 'firmware'),
                     ('description', 'description'), ('posterUrl', 'cover'),
                     ('password', 'password'), ('kind', 'kind'), ('size', 'size')]:
            if package.get(a) is not None:
                entry[b] = package[a]
        result.append(entry)
    return result, 0


def github_releases(source, fetcher):
    repo = source['repository']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('Invalid GitHub repository')
    result = []
    for page in range(1, 21):
        releases = fetcher(f'https://api.github.com/repos/{repo}/releases?per_page=100&page={page}')
        if not isinstance(releases, list):
            raise ValueError('Expected GitHub releases array')
        for release in releases:
            if release.get('draft') or (release.get('prerelease') and not source.get('include_prereleases', False)):
                continue
            for asset in release.get('assets', []):
                if not fnmatch.fnmatchcase(asset['name'], source['asset_pattern']):
                    continue
                checksum = asset.get('digest') or ''
                if not re.fullmatch(r'sha256:[a-fA-F0-9]{64}', checksum):
                    raise ValueError('Release asset lacks GitHub SHA-256 digest')
                url = asset['browser_download_url']
                if not url.startswith(f'https://github.com/{repo}/releases/download/'):
                    raise ValueError('Asset outside developer repository')
                entry = {'title': source['title'], 'title_id': source['title_id'],
                         'version': release['tag_name'].removeprefix('v'), 'platform': 'ps5', 'kind': 'game',
                         'files': [{'url': url, 'name': asset['name'], 'sha256': checksum[7:]}],
                         'size': f"{asset['size']} B", 'description': source.get('description', ''),
                         'atlas': {'repository': f'https://github.com/{repo}', 'license': source['license'],
                                   'released': release.get('published_at'), 'prerelease': release.get('prerelease', False)}}
                if source.get('format'):
                    entry['format'] = source['format']
                for field in ('region', 'firmware', 'cover'):
                    if field in source:
                        entry[field] = source[field]
                entry['atlas']['content_kind'] = source.get('content_kind', 'game')
                entry['atlas']['upstream_format'] = source.get('archive_format') or Path(asset['name']).suffix.lstrip('.').lower()
                result.append(entry)
        if len(releases) < 100:
            return result, 0
    raise ValueError('Release pagination exceeds limit; refusing a partial catalog')


def load_source(source, fetcher):
    adapter = source.get('adapter', 'pegasus')
    if adapter == 'github-releases':
        return github_releases(source, fetcher)
    payload = fetcher(source['url'])
    if adapter == 'homebrew':
        return homebrew(payload, source)
    if adapter == 'pegasus':
        return pegasus(payload, source)
    if adapter == 'native':
        if not isinstance(payload, dict) or not isinstance(payload.get('entries'), list):
            raise ValueError('Expected native entries array')
        return copy.deepcopy(payload['entries']), 0
    raise ValueError('Unknown adapter')


def validate_config(config):
    if not isinstance(config, dict) or not isinstance(config.get('sources'), list):
        raise ValueError('Config needs sources array')
    https_url(config.get('catalog_url'))
    ids = set()
    for source in config['sources']:
        if not isinstance(source, dict):
            raise ValueError('Source must be an object')
        if 'enabled' in source and not isinstance(source['enabled'], bool):
            raise ValueError('enabled must be a boolean')
        sid = source.get('id')
        if not isinstance(sid, str) or not re.fullmatch(r'[a-z0-9-]+', sid) or sid in ids:
            raise ValueError('Source IDs must be unique lowercase slugs')
        ids.add(sid)
        if not source.get('enabled', True):
            continue
        if source.get('adapter', 'pegasus') not in ('native', 'pegasus', 'homebrew', 'github-releases'):
            raise ValueError('Unknown adapter')
        authorization = source.get('authorization', {})
        if authorization.get('status') != 'approved' or not authorization.get('basis'):
            raise ValueError(f'{sid}: enabled source needs authorization evidence')
        https_url(authorization.get('evidence_url'))
        if source.get('adapter') == 'github-releases':
            if 'include_prereleases' in source and not isinstance(source['include_prereleases'], bool):
                raise ValueError('include_prereleases must be a boolean')
            for field in ('license', 'repository', 'title', 'title_id', 'asset_pattern'):
                if not isinstance(source.get(field), str) or not source[field].strip():
                    raise ValueError(f'Developer source needs {field}')
        else:
            https_url(source.get('url'))
        if source.get('adapter') == 'homebrew':
            allowed = source.get('allow_repositories')
            if not isinstance(allowed, list) or not allowed or len(set(allowed)) != len(allowed):
                raise ValueError('Homebrew feed needs unique reviewed repository allowlist')
            for repo in allowed:
                if not isinstance(repo, str) or not re.fullmatch(r'https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
                    raise ValueError('Expected canonical GitHub developer repository')


def entry_identity(entry):
    identity = {k: v for k, v in entry.items() if k not in ('id', 'atlas')}
    # Opaque Pegasus metadata may distinguish editions/backports even when
    # client-facing fields match. Developer identity also disambiguates IDs.
    identity['upstream_identity'] = {k: v for k, v in entry.get('atlas', {}).items()
                                     if k in ('original_package', 'repository')}
    return digest(identity)


def group_identity(entry):
    # Homebrew titles sometimes share a title ID: keep their developers separate.
    return (entry.get('title_id') or entry['title'].casefold(), entry.get('platform', 'ps5'),
            entry.get('kind', 'game'), entry.get('region', ''),
            entry.get('format') or entry.get('atlas', {}).get('upstream_format', ''),
            entry.get('atlas', {}).get('repository', ''))


def history_policy(source):
    """History can survive presentation/allowlist edits, never a new origin or grant."""
    return digest({k: v for k, v in source.items()
                   if k not in ('name', 'description', 'allow_repositories')})


def retained_history(previous, source):
    if (previous.get('fingerprint') != digest(source)
            and previous.get('history_policy') != history_policy(source)):
        return {}
    history = dict(previous.get('history', {}))
    if source.get('adapter') == 'homebrew':
        allowed = source['allow_repositories']
        history = {k: e for k, e in history.items() if e.get('atlas', {}).get('repository') in allowed}
    return history


def version_key(version):
    """Only compare plain numeric versions; never guess ordering for arbitrary release tags."""
    if not isinstance(version, str) or not re.fullmatch(r'v?\d+(?:\.\d+)*', version):
        return None
    parts = [int(n) for n in version.removeprefix('v').split('.')]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def build(config_path, out, fetcher=fetch, now=None):
    now = now or datetime.now(timezone.utc)
    stamp = now.isoformat(timespec='seconds')
    report = {'checked_at': stamp, 'status': 'error', 'sources': []}
    try:
        config = read_json(config_path)
        validate_config(config)
        old = read_json(out / 'catalog-state.json', {'schema': 1, 'sources': {}})
        state = {'schema': 1, 'sources': {}}
        published = {}
        fresh = 0
        for source in sorted(config['sources'], key=lambda s: s['id']):
            sid = source['id']
            if not source.get('enabled', True):
                report['sources'].append({'id': sid, 'status': 'disabled', 'reason': source.get('disabled_reason', '')})
                continue
            fingerprint = digest(source)
            previous = old['sources'].get(sid, {})
            history = retained_history(previous, source)
            past_active = {k: e for k, e in previous.get('active', {}).items() if k in history}
            if previous.get('fingerprint') != fingerprint:
                previous = {}
            stats = {'id': sid}
            try:
                records, skipped = load_source(source, fetcher)
                if not records or len(records) > MAX_RECORDS:
                    raise ValueError('Source empty or exceeds record limit')
                records = [validate_entry(e) for e in records]
                current = {entry_identity(e): e for e in records}
                history.update(current)
                # Preserve older versions only while the same app/region/format is still listed.
                # A removed app or replaced mirror does not remain an active download.
                groups = {}
                for e in current.values():
                    groups.setdefault(group_identity(e), set()).add(e.get('version'))
                active = dict(current)
                for key, entry in past_active.items():
                    versions = groups.get(group_identity(entry))
                    if versions and entry.get('version') and entry['version'] not in versions:
                        active[key] = entry
                cached = {'fingerprint': fingerprint, 'history_policy': history_policy(source), 'last_success': stamp,
                          'current': current, 'active': active, 'history': history}
                stats.update(status='ok', records=len(current), historical_records=len(active)-len(current), filtered=skipped)
                fresh += 1
            except Exception as exc:
                cached = previous
                stats.update(status='error', detail=f'{type(exc).__name__}: {exc}'[:250])
                if previous:
                    age = now - datetime.fromisoformat(previous['last_success'])
                    if timedelta(0) <= age <= timedelta(days=7):
                        stats['status'] = 'stale'
                        stats['last_success'] = previous['last_success']
                    else:
                        stats['cache_expired'] = True
            if cached:
                state['sources'][sid] = cached
            if stats['status'] in ('ok', 'stale'):
                for key, entry in cached['active'].items():
                    record = published.setdefault(key, {'entry': copy.deepcopy(entry), 'sources': [], 'current': False,
                                                       'stale': True})
                    record['sources'].append(sid)
                    record['current'] |= key in cached['current']
                    record['stale'] &= stats['status'] == 'stale'
            report['sources'].append(stats)
        if not fresh or not published:
            raise ValueError('No fresh non-empty source; previous catalog kept unchanged')
        entries = []
        index = []
        maxima = {}
        for record in published.values():
            e = record['entry']
            key = version_key(e.get('version'))
            if key is not None:
                group = group_identity(e)
                maxima[group] = max(maxima.get(group, key), key)
        for key, record in sorted(published.items()):
            entry = record['entry']
            entry['id'] = 'atlas-' + key
            entries.append(entry)
            version = version_key(entry.get('version'))
            index.append({'id': entry['id'], 'title': entry['title'], 'title_id': entry.get('title_id'),
                          'version': entry.get('version'), 'region': entry.get('region'), 'format': entry.get('format'),
                          'sources': sorted(record['sources']), 'status': 'current' if record['current'] else 'historical',
                          'stale': record['stale'], 'latest_in_variant': None if version is None else version == maxima[group_identity(entry)]})
        # Stable version prevents no-op refreshes from changing the client catalog.
        catalog = {'name': 'PS5 Atlas', 'version': digest(entries), 'entries': entries}
        report.update(status='degraded' if any(s['status'] in ('error', 'stale') for s in report['sources']) else 'ok',
                      records=len(entries), catalog_version=catalog['version'])
        write_json(out / 'catalog-state.json', state)
        write_json(out / 'releases.json', {'schema': 1, 'entries': index})
        write_json(out / 'catalog.json', catalog)
        write_json(out / 'sources.json', {'sources': [{'name': 'PS5 Atlas', 'url': config['catalog_url'], 'enabled': True}]})
        code = 0
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'[:300]
        code = 1
    write_json(out / 'build-report.json', report)
    print(json.dumps(report, indent=2))
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'atlas-sources.json')
    parser.add_argument('--output-dir', type=Path, default=ROOT)
    args = parser.parse_args()
    return build(args.config, args.output_dir)


if __name__ == '__main__':
    raise SystemExit(main())
