# Catalog contract and refresh behavior

## Output contract

The primary reference is PS5 Library's [catalog documentation](https://github.com/deox1111/ps5-library#make-your-own-catalog), checked at upstream commit `0d6bc369a4846cd4f358efc2646eb4a33653c941` on 2026-10-21. The documented native shape is:

```json
{"entries":[{"id":"stable-id","title":"App","title_id":"PPSA12345","version":"1.2","files":[{"url":"https://publisher.example/app.zip","name":"app.zip","sha256":"64 hexadecimal characters"}]}]}
```

The schema validator runs offline and checks content-derived IDs, the catalog digest, every source snapshot, configuration fingerprints, release-index provenance and version flags. Checks remain enabled under Python optimization. Use `--config` together with `--root` when validating a separate output directory. This is a contract check, not execution of PS5 Library's console parser. The console has not been contacted or tested.

`atlas` contains additional provenance for inspection; the documented client fields stay at entry level. A homebrew `kind` of `app` or `tool` is recorded as `atlas.content_kind`: the native client documents `game`, `update` and `dlc`, so homebrew titles use `game`. ZIP is an archive/container and is retained as `atlas.upstream_format`, not mislabeled as an exFAT or FFPKG image. Image formats remain separate. No firmware is inferred.

Pegasus's `url`/`filename` and `downloadLinks` forms are converted to native entries. Original packages, including unknown fields and source/backport labels, remain in `atlas.original_package`. Each ordinary link is a mirror. Explicit multipart labels (`part 1`) or filenames (`.part01.rar`, `.7z.001`, `.zip.001`) on one host become one ordered file list; missing or duplicate numbered parts reject the entire source instead of publishing an incomplete download. Atlas cannot infer undocumented multipart conventions.

## Identity and preservation

- Content-derived IDs do not depend on upstream ordering or build timestamps. Only identical client-facing entries deduplicate; versions, regions, formats, files, mirror lists and unknown native fields are not collapsed.
- Every successful source snapshot is saved in `catalog-state.json`. Earlier versions continue in the active catalog while the same title/region/format/developer group still exists. A replaced mirror for the same version or a completely removed app is retained in history, but is no longer published as an active download. Later version updates cannot resurrect such withdrawn links: only previously active records are eligible for retention.
- `releases.json` labels active records `current` or `historical`. Historical means previously observed, not freshly tested. No historical link-availability claim is made.
- Title IDs are combined with developer repository identity where available, so unrelated homebrew apps sharing an ID are not merged. For sources without title IDs, exact case-insensitive titles are the fallback; Atlas does not guess that similarly named editions are one game.
- `latest_in_variant` compares only plain numeric release versions, numerically (`1.10 > 1.9`), within title/platform/kind/region/format/developer groups. Archive containers also distinguish groups when no native image format is given. Unknown tags have `null` and are not ranked. Prerelease flags remain in provenance. It means latest observed listed version, not the latest PlayStation Store version, latest stable release, firmware compatibility, or proof a download works.
- Feed adapters accumulate history from the first successful observation onward. They cannot recover versions never published in that feed. GitHub Releases additionally imports matching historical releases with pagination (100/page, maximum 20 pages); reaching the cap fails rather than silently truncating.

## Failure behavior

All entries of a source are validated before replacing its snapshot. One malformed entry rejects the source as a unit, avoiding silent partial loss. Empty sources also fail as suspicious, so an intentional complete withdrawal requires disabling/removing the source in configuration.

Partial failures retain a matching cached source for seven days; the release index marks it stale. A full source configuration fingerprint prevents stale-cache reuse after any source configuration change. A separate history policy allows accumulated versions to survive presentation changes or homebrew allowlist expansion after a successful fetch; allowlist removal prunes that repository's history. URL, authorization, adapter and other policy changes invalidate history as well. Legacy state acquires this policy on its first successful unchanged refresh.

Disabled/removed sources do not enter the next successful catalog/state. A totally failed build preserves the previously published files, writes a fresh failure report and returns exit code 1. Consequently configuration changes, including removals, take effect in published data on the next successful build; inspect failures immediately if withdrawing authorization.

Live verification checks all fresh current primary/mirror/multipart files against the named GitHub release and its published digest. Stale and retained historical entries are counted as skipped and are not probed. A missing or changed fresh asset fails validation and prevents the workflow from publishing any generated catalog. This prevents the live check from defeating the documented partial-outage fallback.

Each JSON document is written to a temporary file and replaced atomically. Generated outputs are committed together by Git. The client catalog content digest remains stable when entries are unchanged; the build report and snapshot check times still update. Local outputs may change before later validation fails, but Actions publishes none of them after a validation failure.

Fetches have a 35 MB JSON limit, 30-second per-request timeout and up to three attempts for transient errors. Only public HTTPS addresses are accepted, including redirects; local hostnames, non-public literal IPs and credentials in URLs are rejected. Without an HTTPS proxy, DNS addresses are also checked. When an HTTPS proxy resolves the destination, DNS handling is delegated to that configured proxy. There is no console address, discovery, FTP, payload sender or installation operation.

## Source configuration

Common fields are `id`, `name`, `enabled`, `adapter`, and:

```json
{"authorization":{"status":"approved","basis":"Concrete publisher permission or license evidence","evidence_url":"https://publisher.example/LICENSE"}}
```

This is an auditable review record, not an automatic legal determination. Never approve an entire commercial download index merely because it is public. Adapter-specific fields:

| Adapter | Required settings |
| --- | --- |
| `native` | `url` returning `entries` |
| `pegasus` | `url` returning `packages` |
| `homebrew` | `url` returning `apps`, `allow_repositories` reviewed URLs; pinned developer release and license required per imported app |
| `github-releases` | `repository` (`owner/repo`), `title`, `title_id`, `license`, `asset_pattern`; optional boolean `include_prereleases`, `description`, native image `format`, `archive_format`, `content_kind`, `region`, `firmware`, `cover` |

GitHub release assets require a publisher SHA-256 digest. Automatic imports are limited to the approved repository and explicit filename pattern, preventing accidental inclusion of source archives or another platform's binary. New publishers and changed distribution rights still need human review. No private API credentials are used.
