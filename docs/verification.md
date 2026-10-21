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

The implementation was merged through [PR #2](https://github.com/Apisalam/ps5-atlas/pull/2) at commit `fbadc8ea42c79dae670fabbe5b470c4832549111`. Both main workflows completed successfully on 2026-10-21:

- [Main test run 39620792190](https://github.com/Apisalam/ps5-atlas/actions/runs/39620792190): 41 regression tests on each of Python 3.12 and 3.14, offline metadata validation, optimized validation and workflow lint.
- [Main refresh run 39620792121](https://github.com/Apisalam/ps5-atlas/actions/runs/39620792121): 41 generator tests, successful build of seven entries, offline validation, all seven publisher assets/digests verified with zero skips, artifact upload and successful publication.
- The refresh produced bot commit [c3e7f24de6027dd38c0ced395bb7a8a73c08c27e](https://github.com/Apisalam/ps5-atlas/commit/c3e7f24de6027dd38c0ced395bb7a8a73c08c27e). Its build report records status `ok`, seven entries and catalog version `c7dc9006180085885dc321fa2dec495ff80039ea033cce4ee9f9235fa1de30ce`.

Before merge, [branch refresh 39620650530](https://github.com/Apisalam/ps5-atlas/actions/runs/39620650530), [push tests 39620650522](https://github.com/Apisalam/ps5-atlas/actions/runs/39620650522) and [PR tests 39620659075](https://github.com/Apisalam/ps5-atlas/actions/runs/39620659075) also passed. The downloaded branch artifact passed local offline validation and its catalog matched the local generated catalog byte-for-byte. Generated JSON explicitly uses LF on every platform, with a Git attributes rule preserving that encoding of line endings.

After main publication, all five generated JSON documents were fetched from the public `raw.githubusercontent.com/Apisalam/ps5-atlas/main/` addresses. They passed validation together against the approved source config; the public catalog matched the validated GitHub output byte-for-byte. Both advertised client endpoints are present. This verifies the published result in addition to the workflow logs.

CI now additionally lints both workflows with actionlint 1.7.12 and verifies the Linux download against SHA-256 `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`. Regression suites remain serial on one runner per workflow, on Python 3.12 and 3.14. The update workflow saves generated files as an artifact, including on failure; it publishes catalogs only after successful validation on main. A total build failure saves only its error report.

## Verification limits

Only JSON, source/license documentation and release metadata were fetched for catalog research and verification. No game or homebrew binary was downloaded. Publisher hashes were compared as metadata, not independently recomputed from binary bytes. The actionlint executable is a development verification tool, separate from catalog content.

PS5 Library compatibility was checked against its documented native catalog contract at commit `0d6bc369a4846cd4f358efc2646eb4a33653c941`. The console parser and runtime were not executed. No console was discovered, contacted, configured or administered; no payload was sent. No firmware compatibility is claimed.

Stale and retained historical entries are explicitly skipped by live publisher verification; their continued availability is not asserted. Future scheduled runs depend on GitHub Actions availability, and third-party availability or licensing can change. Review additions and rights changes using the evidence in [source research](sources.md).
