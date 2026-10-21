# PS5 Atlas

A PS5 Library-compatible catalog source list and optional Pegasus catalog aggregator.

## Add to PS5 Library

Use **Settings → Catalogs → Add catalog** and paste:

`https://raw.githubusercontent.com/Apisalam/ps5-atlas/main/sources.json`

This points to the three existing sources: DLPS, Pippo and PFS. It does not provide any new games beyond those sources.

## Optional single merged catalog

In **Actions → Update PS5 Atlas catalog → Run workflow**, run the build once. It creates:

`https://raw.githubusercontent.com/Apisalam/ps5-atlas/main/catalog.json`

The build runs on a six-hour schedule thereafter. Add **either** the source-list URL or the merged-catalog URL to PS5 Library, not both.

Distinct source packages are kept, including different versions and mirrors. Only exact duplicate package records are removed. No links are tested for validity, no compatibility with firmware 13.60 is guaranteed, and the build cannot discover newer releases not already listed by the sources.

## Extending the project

Edit `atlas-sources.json` to add an authorized HTTPS Pegasus JSON source with a `packages` array. Run the workflow again.

`build-report.json` records fetch errors; if all sources fail, the workflow will not overwrite the previous catalog.

This is a **public** repository: never commit personal access tokens or private account details. Do not add unlicensed links you lack permission to redistribute.
