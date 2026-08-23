# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
