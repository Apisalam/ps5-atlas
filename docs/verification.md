# Verification evidence — 2026-10-21

## Current implementation

The expanded catalog contains seven titles from five enabled sources: three reviewed feed records and four developer-release records. All four original content IDs remain present. DLPS, Pippo and PFS remain disabled. There were no open repository issues or pull requests at the start of this continuation.

Local verification on Windows with Python 3.14.2:

- 41 offline regression tests passed, covering generator, publisher checks and the output contract.
- All 41 regressions also passed with Python optimization enabled; optimization cannot disable the validator's rejection checks.
- Both workflows passed actionlint 1.7.12, using the upstream Windows release verified against SHA-256 `6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9`.
- All seven current assets matched their named developer release, published state and SHA-256 metadata.
- An unchanged repeat refresh produced byte-for-byte identical `catalog.json`.
- Offline validation confirmed content IDs, digest, source fingerprints, current/active/history snapshots, release-index provenance and numeric latest-version flags.
- All three added sources refreshed successfully; the reviewed feed filtered 100 unapproved records.

The new regressions cover allowlist expansion/removal, preservation of history across presentation edits, invalidation of stale cache on any config change, superseded mirror resurrection, deterministic provenance across source ordering, archive grouping, homebrew region/firmware, Pegasus password/checksum propagation, all alternative mirror files, stale/historical verification skips, uppercase checksum equivalence, native field/mirror types, optimized validation, isolated output configuration, duplicate/tampered release indices and native upstream IDs.

## GitHub Actions

Current expansion runs will be recorded here after execution. The branch update workflow builds and uploads evidence without publishing. Once merged, the main update workflow additionally commits validated generated metadata.

Earlier verified baseline runs (four titles, 23 tests) remain available as historical evidence:

- [Update workflow 39615294107](https://github.com/Apisalam/ps5-atlas/actions/runs/39615294107): successful build, validation, metadata verification, artifact upload and bot commit.
- [Test workflow 39617775971](https://github.com/Apisalam/ps5-atlas/actions/runs/39617775971): successful Python 3.12 and 3.14 checks.

Earlier failed attempts were rejected before runner startup. The successful baseline runs superseded that infrastructure blocker; they do not establish the expanded implementation's result.

CI now additionally lints both workflows with actionlint 1.7.12 and verifies the Linux download against SHA-256 `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`. Regression suites remain serial on one runner per workflow, on Python 3.12 and 3.14. The update workflow saves generated files as an artifact, including on failure; it publishes catalogs only after successful validation on main. A total build failure saves only its error report.

## Verification limits

Only JSON, source/license documentation and release metadata were fetched for catalog research and verification. No game or homebrew binary was downloaded. Publisher hashes were compared as metadata, not independently recomputed from binary bytes. The actionlint executable is a development verification tool, separate from catalog content.

PS5 Library compatibility was checked against its documented native catalog contract at commit `0d6bc369a4846cd4f358efc2646eb4a33653c941`. The console parser and runtime were not executed. No console was discovered, contacted, configured or administered; no payload was sent. No firmware compatibility is claimed.

Stale and retained historical entries are explicitly skipped by live publisher verification; their continued availability is not asserted. Future scheduled runs depend on GitHub Actions availability, and third-party availability or licensing can change. Review additions and rights changes using the evidence in [source research](sources.md).
