# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

## [1.0.0] - 2026-08-20

### Added
- Initial release: nightly CKAN fetch, RFC 5545-compliant ICS generation with
  deterministic SHA-256 UIDs, sanity gate before deployment, GitHub Pages hosting
