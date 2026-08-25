# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **«Zu Google Kalender hinzufügen» führte zu «Hinzufügen zum Kalender nicht
  möglich. Überprüfen Sie die URL.»** Der Link übergab die Feed-Adresse als
  `cid=https://…`, unkodiert. Google verlangt für ein Abo auf eine fremde
  `.ics`-Datei das `webcal`-Schema und den Wert prozentkodiert; mit `https`
  bricht die Oberfläche mit genau dieser Meldung ab. Landing-Page und beide
  READMEs verweisen jetzt auf
  `cid=webcal%3A%2F%2Fmalkreide.github.io%2Fzuerich-schulferien-ics%2Fferien.ics`.
  Der Feed selbst war nie betroffen — er liefert unverändert HTTP 200 mit
  `Content-Type: text/calendar`. Dazu auf der Seite ein Weg von Hand
  (*Weitere Kalender → + → Per URL*) für den Fall, dass der Link erneut klemmt.

Four findings from a second pass over `scripts/compare_official_ics.py`, which
shipped without an external review. All four are latent — none changes today's
result (104 records identical, no drift) — but each would misfire the first
time the source changed shape.

- **A run that recognises no school record now fails instead of reassuring.**
  If the city renames the `Schulen Stadt Zürich` prefix in *both* exports, they
  still match each other perfectly: no drift is found, and the script printed
  `OK` for a source that had just emptied the feed. `generate_ics.py` catches
  that at `MIN_SCHOOL_SHARE`, but only after somebody had already trusted this
  run. The report now carries the recognised-record count per export
  (`.ics 51, CKAN 47` today) and exits 2 when either is zero. This was the only
  finding whose failure mode was *quiet*.
- **Titles are Unicode-normalised (NFC) before comparison.** `ü` has a
  precomposed and a decomposed encoding, and the two exports come from
  different tooling — the `.ics` files out of Outlook. Both use NFC today, but
  if either switched, every record containing `Zürich` (nearly all of them)
  would be reported as drift in both directions at once. It would also have
  stopped matching `SCHOOL_RECORD_RE`, whose pattern contains a literal `ü`.
- **`parse_ics` no longer crashes on a valid `.ics` it does not expect.**
  Reading `DTEND` unconditionally raised `KeyError` on an event carrying
  `DURATION` instead, or neither — both allowed by RFC 5545. `DURATION` is now
  honoured and a bare `DATE` start is read as a one-day event per §3.6.1. An
  event without `SUMMARY` or `DTSTART` is refused loudly rather than skipped,
  since skipping would shrink the comparison without saying so.
- **A rescheduled holiday reads as one move, not two problems.** A changed date
  lands in both unexplained sets; the report now pairs same-title entries and
  prints the two spans together. Presentation only — both entries still count
  as drift.

### Added
- `scripts/compare_official_ics.py` — cross-checks the city's official
  per-school-year `.ics` downloads against the CKAN dataset the feed is built
  from. The City of Zurich publishes the same dates twice, from separate
  exports, and nothing guarantees they stay in step. The script scrapes the
  download links off the Schulferien page (hard-coding them would silently
  compare fewer years each year), classifies the two *expected* differences,
  and exits non-zero when a school record appears in one export but not the
  other. Needs network, so it stays out of the offline `pytest` gate; the
  parsing and classification logic is covered by
  `tests/test_compare_official_ics.py` (23 tests).

  First run, 2026-08-24, over all four offered school years (2026/27–2029/30):
  **104 records identical, zero unexplained differences in either direction.**
  The two expected classes: four summer holidays that the per-year files cut
  at the 1 August school-year boundary where CKAN carries the whole block
  (`2026-07-13 → 2026-08-15` versus `2026-08-01 → 2026-08-15`), and one
  same-span duplicate in CKAN (`Pfingsten` alongside `Pfingstsonntag` on
  2029-05-20). CKAN is thus the more complete of the two exports, and a
  manual `.ics` handover adds nothing the feed does not already have.
- Failure alarm: a nightly run that fails now opens an issue — or comments on
  the open one — instead of failing silently. The sanity gate deliberately
  leaves the last known-good feed on Pages, which means a broken source looks
  exactly like a working one from the outside until somebody opens the Actions
  tab. Matching is on the exact issue title via the issues API rather than the
  search API, whose eventual consistency would open a fresh issue every night.
  Pull requests are excluded — a red check is already visible there.
- Keepalive workflow: a monthly heartbeat commit to `.github/last-heartbeat`.
  GitHub disables scheduled workflows in a public repository after 60 days
  without repository activity, and workflow runs do not count — so a feed that
  simply works, with nobody pushing to it, switches itself off after two quiet
  months without anything turning red. GitHub does not document what counts as
  activity, so this is a mitigation rather than a guarantee; the warning mail
  GitHub sends before disabling remains the authoritative signal.

### Changed
- The `push` trigger on `deploy.yml` ignores `.github/last-heartbeat`, so the
  heartbeat does not cost a second build and deploy on top of the nightly one.

## [2.0.0] - 2026-08-23

Reshapes the feed around the people who use it: parents with children in
Zurich's public schools. **What existing subscribers will notice:** 97 public
holidays disappear from `ferien.ics`, every event title gets shorter, and
`Schulschluss 12 Uhr` moves from an all-day bar to a timed entry at noon. The
76 school events keep their UIDs, so calendars update in place rather than
resyncing. Hence the major version — the published feed's contents changed,
even though no URL did.

### Added
- `Schulschluss 12 Uhr` is published as a *timed* event at 12:00 Europe/Zurich
  (with a matching `VTIMEZONE`) instead of an all-day event. It is the one entry
  where the day is *not* free, and rendering it like a holiday is exactly what a
  parent misreads. A multi-day record carrying that title stays all-day rather
  than collapsing to a single noon.
- Two further feeds alongside the existing one, all built from the same fetch:
  `nur-ferien.ics` (only the multi-day closures — no single days like
  Knabenschiessen or the first day of school) and `alles.ics` (additionally the
  public holidays from the same dataset). `ferien.ics` is deliberately
  **unchanged** in scope: it is the advertised, already-subscribed URL, and
  narrowing it would strip dates from calendars without anyone asking. The three
  nest (`nur-ferien` ⊂ `ferien` ⊂ `alles`) and an event keeps one UID across all
  of them. The landing page offers all three.
- Year overview on the landing page: the current and next school year as tables,
  rendered from the same events as the feed. Most visitors want to look a date up
  rather than subscribe, and that was not served at all. Building it from the
  feed's own events means the page can never show a date the feed does not
  contain.
- Event `DESCRIPTION` for entries whose title was shortened and for the half-day
  events, so no source wording is lost.
- Fixture-based `pytest` suite (`tests/`, 96 tests) covering the
  exclusive-`end_date` convention, the school filter, title cleanup, half-day
  handling, the cutoff, UID stability, the feed variants, both sanity gates and
  landing-page rendering. Runs offline, so a CKAN outage cannot turn it red.
- `requirements-dev.txt` for the test and lint toolchain.
- CI runs on `pull_request` too, with `ruff` and the test suite gating the build.
  The workflow previously triggered only on push to `main`, `schedule` and
  `workflow_dispatch`, so the test job could never block a pull request —
  failures would only have surfaced after the merge. `build` and `deploy` are
  skipped on pull requests: no Pages deployment from a branch, and no dependency
  on the live CKAN API that could turn a review red.
- Forward-coverage gate: the build fails when the source reaches less than
  `MIN_FORWARD_COVERAGE_DAYS` (180) ahead. `latest_end < today` alone only fired
  once the data was *entirely* historic — by which point parents had been
  planning against a feed that had quietly run out. Against the current data the
  first failure would be 2030-02-19, about six months before the source ends.
- Running-school-year gate: the school year containing today must carry at least
  `MIN_EVENTS_CURRENT_YEAR` (5) events, catching a source that keeps far-future
  entries but drops the current year.
- Sanity gate rejects a feed where fewer than 30% of fetched records match the
  school prefix, catching a rename at the source instead of shipping an empty
  calendar.

### Changed
- Only records prefixed `Schulen Stadt Zürich` reach the default feed. The
  source mixes school dates with plain public holidays; in the current window
  that is 76 school entries against 97 holidays, of which 94 fall entirely
  inside an already school-free block and 22 land on weekends only. Publishing
  them buried the dates the feed exists for under duplicates.
- Event titles are cleaned for display: the `Schulen Stadt Zürich schulfrei:`
  prefix is dropped (the calendar is already named) and a trailing parenthetical
  moves into `DESCRIPTION`. The longest title drops from 137 to 42 characters,
  so a month view shows "Frühlingsferien" rather than "Schulen Sta…".
- `DTSTAMP` comes from the source record's `created_date` instead of the wall
  clock. Every nightly run previously emitted a byte-different file even when
  nothing had changed, rotating the ETag so every subscriber re-downloaded the
  whole feed. Identical input now produces identical bytes. Comparing against
  the previously deployed file was not an option: CI checks out a fresh tree and
  `public/` is generated, so there is nothing to compare against.
- UIDs hash the *raw* source summary rather than the cleaned title, so the title
  cleanup updates existing subscriptions in place. Verified against the deployed
  feed: all 76 retained events keep their UID.
- Half-day detection tolerates a reworded source (`um 12.00 Uhr`, `um 12:00
  Uhr`, trailing qualifiers). The previous pattern was anchored end to end, so a
  rewording would have silently reverted the entry to an all-day event — a
  school day rendered as a day off, the exact failure that branch prevents. Any
  extra wording is preserved in the description.
- `sanity_check` split into `check_source` (gates the fetched data once) and
  `check_feed` (gates each generated file, including a duplicate-UID check), and
  takes the run date as an argument instead of reading the clock, which makes
  the staleness gate testable without patching. `MIN_EXPECTED_PUBLISHED` raised
  from 10 to 20.
- Landing page and both READMEs state what the feed deliberately does not cover
  — public holidays, school-specific dates, and childcare opening hours. The
  last matters most: school-free does not mean after-school care is closed, and
  no open data exists for it.

### Fixed
- UIDs for records shipping `end_date == start_date` are hashed from the
  *normalised* end date, matching what the feed has always published. The
  rewrite moved the hash ahead of that normalisation, which would have handed
  each such record a new UID and resynced it for every subscriber. All six
  affected rows in the source predate the cutoff, so no deployed UID changed —
  the defect was latent until the city files the next one inside the window.
- A half-day title that differs from the canonical form only in spelling
  (`Schulschluss um 12 Uhr` vs `Schulschluss 12 Uhr`) no longer repeats itself
  in the description. Four events in the deployed feed carried
  `Der Unterricht endet an diesem Tag um 12 Uhr. Schulschluss um 12 Uhr`.
  Wording that survives the spelling-variant folding is still kept.

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
