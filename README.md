# PS5 Atlas

A public, metadata-only catalog generator for [PS5 Library](https://github.com/deox1111/ps5-library). It reads reviewed homebrew feeds and developer releases, preserves release variants, and refreshes every six hours with GitHub Actions. It does not discover, connect to, or modify a PS5, and never downloads game binaries.

## Catalog addresses

Use either the merged catalog:

`https://raw.githubusercontent.com/Apisalam/ps5-atlas/main/catalog.json`

or the compatible source list (which points to that same catalog):

`https://raw.githubusercontent.com/Apisalam/ps5-atlas/main/sources.json`

Add only one of these in PS5 Library's Settings → Catalogs. This repository makes no changes to an existing console configuration. Older copies of `sources.json` named DLPS, Pippo and PFS directly; already-added upstream catalogs are not changed or removed remotely by Atlas.

The catalog uses PS5 Library's documented native `entries` / `files` shape. SHA-256 values are retained on each file. PS5 Library 0.7.37 or newer documents verification of these hashes. Compatibility here means **catalog format compatibility**, not a promise that an app runs on any particular console, firmware, loader or installer. See [source research](docs/sources.md) and [catalog behavior](docs/catalog.md).

## Current coverage

The reviewed seed set contains **SuperTuxKart, ccleste (Celeste Classic), Middle Ages Ping Pong and ProsperoLight**. It is a deliberately small authorized homebrew set, not a complete commercial PS5 games library. Newly discovered publishers require review before import; existing approved sources refresh automatically.

The three original sources remain in `atlas-sources.json`, disabled: public reachability was tested, but permission to redistribute their downloads was not established. Public availability alone is not treated as authorization.

## Build and verify

Python 3.12 or newer; standard library only:

```sh
python -m unittest discover -s tests -v
python scripts/build.py
python scripts/validate.py
python scripts/check_links.py
```

`check_links.py` checks the seeded GitHub release assets against current publisher metadata, including SHA-256. It fetches metadata only, not binaries. It intentionally fails for non-GitHub files; review a separate verification method before enabling such sources.

Use `python scripts/build.py --config path/to/config.json --output-dir path/to/output` for an isolated build. No code depends on the working directory.

Generated files:

| File | Purpose |
| --- | --- |
| `catalog.json` | PS5 Library native download entries; stable IDs and content version |
| `sources.json` | Client source list pointing to `catalog.json` |
| `releases.json` | Current/historical status, source provenance, stale flags, latest version per variant |
| `catalog-state.json` | Per-source successful snapshots and accumulated release history |
| `build-report.json` | Most recent attempt, counts, filtered records and source failures |

## Automatic refresh

**Update PS5 Atlas catalog** runs at minute 17 every six hours (UTC), on relevant pushes, and through **Actions → Run workflow**. GitHub schedules may be delayed. Only successful validation on `main` can publish generated catalogs. Feature branches build and upload artifacts without pushing. CI runs offline regression tests on Python 3.12 and 3.14.

A partial outage uses that source's last successful snapshot for up to seven days and reports `degraded`/`stale`. If no source is fresh, the build exits unsuccessfully and preserves the prior catalog. The workflow still saves its failure report and uploads evidence. Failed schema validation prevents publication. Action versions are pinned to commit SHAs, jobs have time limits, and refreshes on a branch are serialized.

## Add an authorized source

Edit `atlas-sources.json` with a unique `id`, adapter and authorization evidence. Available adapters: `native` (`entries`), `pegasus` (`packages`), `homebrew` (`apps` with a reviewed repository allowlist), and `github-releases` (all published matching assets, paginated). See [configuration and history rules](docs/catalog.md). Adding another source using these formats requires configuration changes only.

Never commit access tokens, account details, private links or downloadable content you lack permission to redistribute. Developer software and assets retain their original licenses; this repository links to releases and does not rehost their files.
