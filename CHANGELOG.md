# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Year overview on the landing page: the current and next school year as
  tables, rendered from the same events as the feed. Most visitors want to look
  a date up rather than subscribe, and that was not served at all. Building it
  from the feed's own events means the page can never show a date the feed does
  not contain.

### Changed
- `DTSTAMP` comes from the source record's `created_date` instead of the wall
  clock. Every nightly run previously emitted a byte-different file even when
  nothing had changed, rotating the ETag so every subscriber re-downloaded the
  whole feed. Identical input now produces identical bytes. Comparing against
  the previously deployed file was not an option: CI checks out a fresh tree
  and `public/` is generated, so there is nothing to compare against.

### Fixed
- A half-day title that differs from the canonical form only in spelling
  (`Schulschluss um 12 Uhr` vs `Schulschluss 12 Uhr`) no longer repeats itself
  in the description. Four events in the deployed feed carried
  `Der Unterricht endet an diesem Tag um 12 Uhr. Schulschluss um 12 Uhr`.
  Wording that survives the spelling-variant folding is still kept.

### Added
- `Schulschluss 12 Uhr` is now published as a timed event at 12:00
  Europe/Zurich (with a matching `VTIMEZONE`) instead of an all-day event.
  It was the one entry where the day is *not* free, and rendering it like a
  holiday is exactly what a parent misreads. A multi-day record carrying that
  title is left as an all-day event rather than collapsed to a single noon.
- Event `DESCRIPTION` for entries whose title was shortened and for the
  half-day events, so no source wording is lost.
- Fixture-based `pytest` suite (`tests/`) covering the exclusive-`end_date`
  convention, the school filter, title cleanup, half-day handling, the cutoff,
  UID stability, the sanity gate and landing-page rendering. Runs offline, so a
  CKAN outage cannot turn it red. CI runs it — plus `ruff` — before the build
  job, so a failing test blocks deployment.
- `requirements-dev.txt` for the test and lint toolchain.
- CI runs on `pull_request` too. The workflow previously triggered only on
  push to `main`, `schedule` and `workflow_dispatch`, so the test job could
  never block a pull request — failures would only have surfaced after the
  merge. `build` and `deploy` are skipped on pull requests: no Pages
  deployment from a branch, and no dependency on the live CKAN API that could
  turn a review red.
- Sanity gate rejects a feed where fewer than 30% of fetched records match the
  school prefix, catching a rename at the source instead of shipping an empty
  calendar. `MIN_EXPECTED_PUBLISHED` raised from 10 to 20.

### Changed
- Only records prefixed `Schulen Stadt Zürich` are published. The source mixes
  school dates with plain public holidays; in the current window that is 76
  school entries against 97 holidays, of which 94 fall entirely inside an
  already school-free block and 22 land on weekends only. Publishing them
  buried the dates the feed exists for under duplicates.
- Event titles are cleaned for display: the `Schulen Stadt Zürich schulfrei:`
  prefix is dropped (the calendar is already named) and a trailing parenthetical
  moves into `DESCRIPTION`. The longest title drops from 137 to 42 characters,
  so a month view shows "Frühlingsferien" rather than "Schulen Sta…".
- UIDs now hash the *raw* source summary rather than the cleaned title, so the
  title cleanup updates existing subscriptions in place. Verified against the
  deployed feed: all 76 retained events keep their UID.
- Landing page and both READMEs state what the feed deliberately does not cover
  — public holidays, school-specific dates, and childcare opening hours.
- Half-day detection tolerates a reworded source (`um 12.00 Uhr`, `um 12:00
  Uhr`, trailing qualifiers). The previous pattern was anchored end to end, so
  a rewording would have silently reverted the entry to an all-day event — a
  school day rendered as a day off, the exact failure this branch prevents.
  Any extra wording is preserved in the description.
- `sanity_check` takes the run date as an argument instead of reading the clock,
  which makes the staleness gate testable without patching.

### Fixed
- UIDs for records shipping `end_date == start_date` are hashed from the
  *normalised* end date, matching what the feed has always published. The
  rewrite moved the hash ahead of that normalisation, which would have handed
  each such record a new UID and resynced it for every subscriber. All six
  affected rows in the source currently predate the cutoff, so no deployed UID
  changed — the defect was latent until the city filed the next one inside the
  window. Verified against the deployed feed: 76 of 76 retained events keep
  their UID, 0 new.

## [1.1.0] - 2026-08-23

### Added
- Cutoff: only events reaching into the current or the two preceding calendar
  years are published (`CUTOFF_YEARS_BACK = 2`). The source starts in 2018, which buried subscribers under years of
  past entries. An event straddling the cutoff is kept in full. Retained events
  keep their UIDs, so existing subscriptions see no re-sync.
- Sanity gate rejects a feed where fewer than `MIN_EXPECTED_PUBLISHED` events
  survive the cutoff.
- Landing page at the Pages root, replacing the previous 404. Template lives in
  `web/index.html` and is rendered into `public/` by `generate_ics.py`, so the
  event count and coverage end date it shows come from the same run that built
  the feed instead of being maintained by hand. An unresolved placeholder fails
  the build rather than reaching subscribers.

### Changed
- Docs: added a "Verifying the feed" section covering the missing `charset`
  parameter on GitHub Pages and how to fetch the feed correctly in PowerShell.
- CI pins all GitHub Actions to full commit SHAs, keeping the major version as a
  trailing comment so Dependabot still updates them.
- Author name filled in across `LICENSE`, both READMEs and `.github/repo-meta.yml`,
  replacing the `{AUTHOR_LEGAL_NAME}` placeholder.

## [1.0.0] - 2026-08-22

### Added
- Initial release: nightly CKAN fetch, RFC 5545-compliant ICS generation with
  deterministic SHA-256 UIDs, sanity gate before deployment, GitHub Pages hosting
