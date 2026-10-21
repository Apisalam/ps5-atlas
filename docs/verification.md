# Verification evidence — 2026-10-21

## Completed locally

| Check | Result |
| --- | --- |
| Original generator | 3,206 package records fetched from its three configured endpoints; no binaries fetched |
| Regression suite, Python 3.12 | 23 tests passed |
| Regression suite, Python 3.14.8 | The same 23 tests passed |
| Workflow lint | actionlint 1.7.12 passed for both workflows |
| Native catalog contract | 4 entries, unique IDs, valid HTTPS links/hashes, matching release index, source list and approved source state |
| Live rebuilt catalog | 3 allowlisted homebrew-feed records and 1 developer-release record |
| Publisher asset verification | All 4 file URLs exist in the named published GitHub releases; all 4 SHA-256 values match GitHub's asset metadata |
| Repeat refresh | Client catalog stays byte-for-byte identical for unchanged records; report/check timestamps can change |
| Console operations | None: no console discovery, connection, upload, payload execution or settings changes |

The tests cover total/partial outages, stale cache expiration, configuration changes, disabled sources, malformed/empty sources, duplicate records, source ordering, versions/regions/formats/mirrors, opaque Pegasus edition metadata, ordered multipart archives, historical releases, removed apps/mirrors, GitHub release pagination/drafts/prereleases/digests, public HTTPS restrictions, retry/size limits and publisher verification failures.

## GitHub Actions attempt

The first branch push started workflow records but every job was rejected **before runner startup**, with no executed steps. GitHub reported an account-level restriction. This is infrastructure/account blocking, not a passing cloud test and not evidence of a code/test failure.

- [Update workflow attempt](https://github.com/Apisalam/ps5-atlas/actions/runs/39614701756)
- [Python matrix workflow attempt](https://github.com/Apisalam/ps5-atlas/actions/runs/39614701708)
- [Change review](https://github.com/Apisalam/ps5-atlas/pull/1)

The workflow definitions are syntax-checked locally, contain real test/build/validation steps, and configure a six-hour schedule on main. Successful cloud execution, artifact upload and bot publication remain unverified until GitHub Actions is available again. Once restored, run **Update PS5 Atlas catalog** on main and inspect both its validation steps and the resulting generated metadata commit.

## Limits of this verification

Metadata only: no binary bytes were downloaded, so this does not independently recompute file hashes. The client retains the expected hashes for its own download verification. PS5 Library compatibility was checked against the documented JSON contract; its console parser and application runtime were not executed. No firmware compatibility is claimed. Third-party availability and licensing may change after this snapshot.

## Follow-up: verified GitHub runner execution

On 2026-10-21, [Update PS5 Atlas catalog run 39615294107](https://github.com/Apisalam/ps5-atlas/actions/runs/39615294107) completed successfully on `main`. The runner executed checkout, Python setup, generator tests, building, schema validation, metadata/link verification, artifact upload and a generated metadata commit (`c675e39b2e85e9d03f9baa865e1bccf6e33bd123`). The checked-in build report records 4 entries and source status `ok` at 2026-10-21T14:24:48Z. This supersedes the original account-level blocker for the update workflow. A single successful scheduled-capable run does not prove future cron reliability or native console runtime compatibility.

The standalone test workflow was modified in commit `6968d2717b842c2d24a75e9da70b5d5caff87903` to run Python 3.12 and 3.14 serially on one runner, add manual dispatch, and avoid concurrent runner allocation. Its new cloud outcome must be checked independently; earlier failed runs had empty runner steps.
