"""Offline tests for the cross-source comparison in ``scripts/``.

The script itself needs network access; everything worth guarding in it is
pure. These tests pin the two "expected difference" rules, because both are
exemptions — a rule written too loosely would swallow real drift and report
a clean run.
"""

from __future__ import annotations

import unicodedata
from datetime import date

import pytest

from scripts.compare_official_ics import (
    Entry,
    classify,
    discover_ics_urls,
    normalise,
    parse_ics,
    records_to_entries,
)

SOMMERFERIEN = "Schulen Stadt Zürich: Sommerferien (KW 29-33)"


def entry(start: str, end: str, summary: str) -> Entry:
    return Entry(date.fromisoformat(start), date.fromisoformat(end), summary)


def ics_bytes(*events: tuple[str, str, str]) -> bytes:
    body = "".join(
        "BEGIN:VEVENT\r\n"
        f"DTSTART;VALUE=DATE:{start.replace('-', '')}\r\n"
        f"DTEND;VALUE=DATE:{end.replace('-', '')}\r\n"
        f"SUMMARY;LANGUAGE=de-ch:{summary}\r\n"
        "END:VEVENT\r\n"
        for start, end, summary in events
    )
    return f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n{body}END:VCALENDAR\r\n".encode()


class TestDiscoverIcsUrls:
    def test_relative_hrefs_become_absolute(self) -> None:
        html = '<a href="/content/dam/schulferien-2026-2027.ics">Termindatei</a>'
        assert discover_ics_urls(html) == [
            "https://www.stadt-zuerich.ch/content/dam/schulferien-2026-2027.ics"
        ]

    def test_pdfs_and_other_links_are_ignored(self) -> None:
        html = '<a href="/a.pdf">x</a><a href="/b.ics">y</a><a href="/c.html">z</a>'
        assert [u.rsplit("/", 1)[-1] for u in discover_ics_urls(html)] == ["b.ics"]

    def test_duplicate_links_collapse_but_order_survives(self) -> None:
        html = '<a href="/b.ics"></a><a href="/a.ics"></a><a href="/b.ics"></a>'
        assert [u.rsplit("/", 1)[-1] for u in discover_ics_urls(html)] == [
            "b.ics",
            "a.ics",
        ]

    def test_a_page_without_downloads_yields_nothing(self) -> None:
        # main() turns this into a hard error: silently comparing zero files
        # would report a clean run against no data at all.
        assert discover_ics_urls("<p>Die Termindateien folgen später.</p>") == []


class TestNormalise:
    def test_trailing_space_is_not_drift(self) -> None:
        # Two of the city's real records carry one; CKAN's do not.
        assert normalise("Frühlingsferien ") == normalise("Frühlingsferien")

    def test_inner_whitespace_collapses(self) -> None:
        assert normalise("Sommerferien  (KW\t29-33)") == "Sommerferien (KW 29-33)"

    def test_wording_differences_survive(self) -> None:
        assert normalise("Pfingsten") != normalise("Pfingstsonntag")


class TestParseIcs:
    def test_all_day_event_keeps_exclusive_end(self) -> None:
        parsed = parse_ics(ics_bytes(("2026-10-05", "2026-10-17", "Herbstferien")))
        assert parsed == {entry("2026-10-05", "2026-10-17", "Herbstferien")}

    def test_summary_is_normalised_on_the_way_in(self) -> None:
        parsed = parse_ics(ics_bytes(("2028-04-17", "2028-04-29", "Frühlingsferien ")))
        assert next(iter(parsed)).summary == "Frühlingsferien"


class TestRecordsToEntries:
    def test_ckan_timestamps_reduce_to_dates(self) -> None:
        records = [
            {
                "start_date": "2026-02-09T00:00:00Z",
                "end_date": "2026-02-21T00:00:00Z",
                "summary": "Schulen Stadt Zürich: Sportferien",
            }
        ]
        assert records_to_entries(records) == {
            entry("2026-02-09", "2026-02-21", "Schulen Stadt Zürich: Sportferien")
        }


class TestEntry:
    def test_school_prefix_is_recognised(self) -> None:
        assert entry(
            "2026-10-05", "2026-10-17", "Schulen Stadt Zürich: Herbstferien"
        ).school

    def test_plain_holiday_is_not_a_school_record(self) -> None:
        assert not entry("2029-05-20", "2029-05-21", "Pfingsten").school


class TestClassify:
    def test_identical_exports_report_no_difference(self) -> None:
        both = {entry("2026-10-05", "2026-10-17", "Schulen Stadt Zürich: Herbstferien")}
        report = classify(both, both)
        assert report.matched == both
        assert not report.only_ics and not report.only_ckan
        assert not report.drifted

    def test_summer_holiday_cut_at_the_school_year_boundary_is_explained(self) -> None:
        city = {entry("2026-08-01", "2026-08-15", SOMMERFERIEN)}
        ckan = {entry("2026-07-13", "2026-08-15", SOMMERFERIEN)}
        report = classify(city, ckan)
        assert report.truncated == city
        assert not report.only_ics
        assert not report.drifted

    def test_a_shortened_end_is_drift_not_truncation(self) -> None:
        # Same title, later start — but the city's copy also ends earlier, so
        # CKAN does not hold the same event over a longer span.
        city = {entry("2026-08-01", "2026-08-10", SOMMERFERIEN)}
        ckan = {entry("2026-07-13", "2026-08-15", SOMMERFERIEN)}
        report = classify(city, ckan)
        assert not report.truncated
        assert report.drifted == city

    def test_same_span_duplicate_in_ckan_is_explained(self) -> None:
        shared = entry("2029-05-20", "2029-05-21", "Pfingsten")
        city = {shared}
        ckan = {shared, entry("2029-05-20", "2029-05-21", "Pfingstsonntag")}
        report = classify(city, ckan)
        assert report.duplicated == {
            entry("2029-05-20", "2029-05-21", "Pfingstsonntag")
        }
        assert not report.only_ckan

    def test_two_extra_ckan_records_do_not_explain_each_other(self) -> None:
        # The exemption asks whether the twin is in the *city's* export. Drop
        # that and a pair of same-span records missing from the city file
        # would cancel each other out, hiding both.
        city = {
            entry("2029-05-14", "2029-05-15", "Schulen Stadt Zürich: Weiterbildung"),
            entry("2029-06-10", "2029-06-11", "Schulen Stadt Zürich: Projekttag"),
        }
        twins = {
            entry(
                "2029-05-20", "2029-05-22", "Schulen Stadt Zürich schulfrei: Pfingsten"
            ),
            entry("2029-05-20", "2029-05-22", "Schulen Stadt Zürich: Pfingstbrücke"),
        }
        report = classify(city, city | twins)
        assert not report.duplicated
        assert report.drifted == twins

    def test_a_lone_extra_ckan_record_is_not_a_duplicate(self) -> None:
        # No twin in the city's export, so the exemption must not apply.
        city = {
            entry("2029-05-20", "2029-05-21", "Pfingsten"),
            entry("2029-06-10", "2029-06-11", "Schulen Stadt Zürich: Weiterbildung"),
        }
        ckan = city | {
            entry("2029-05-28", "2029-05-29", "Schulen Stadt Zürich: Brücke")
        }
        report = classify(city, ckan)
        assert not report.duplicated
        assert report.drifted == {
            entry("2029-05-28", "2029-05-29", "Schulen Stadt Zürich: Brücke")
        }

    def test_records_outside_the_published_window_are_ignored(self) -> None:
        # CKAN reaches back to 2018; the city only offers upcoming years.
        city = {entry("2026-10-05", "2026-10-17", "Schulen Stadt Zürich: Herbstferien")}
        ckan = city | {
            entry("2018-08-01", "2018-08-18", "Schulen Stadt Zürich: Sommerferien")
        }
        report = classify(city, ckan)
        assert not report.only_ckan
        assert not report.drifted

    def test_missing_school_record_is_drift(self) -> None:
        city = {
            entry("2026-10-05", "2026-10-17", "Schulen Stadt Zürich: Herbstferien"),
            entry("2026-12-19", "2027-01-04", "Schulen Stadt Zürich: Weihnachtsferien"),
        }
        ckan = {entry("2026-10-05", "2026-10-17", "Schulen Stadt Zürich: Herbstferien")}
        report = classify(city, ckan)
        assert report.drifted == {
            entry("2026-12-19", "2027-01-04", "Schulen Stadt Zürich: Weihnachtsferien")
        }

    def test_holiday_only_difference_is_reported_but_not_drift(self) -> None:
        city = {
            entry("2026-10-05", "2026-10-17", "Schulen Stadt Zürich: Herbstferien"),
            entry("2026-12-19", "2027-01-04", "Schulen Stadt Zürich: Weihnachtsferien"),
        }
        ckan = city | {entry("2026-11-01", "2026-11-02", "Allerheiligen")}
        report = classify(city, ckan)
        assert report.only_ckan == {entry("2026-11-01", "2026-11-02", "Allerheiligen")}
        assert not report.drifted

    def test_ckan_records_after_the_last_offered_year_are_ignored(self) -> None:
        # The city stops publishing where its files stop; CKAN reaches further.
        # Treating that as "missing from the .ics" would fail every run.
        city = {entry("2026-10-05", "2026-10-17", "Schulen Stadt Zürich: Herbstferien")}
        ckan = city | {
            entry("2031-10-04", "2031-10-16", "Schulen Stadt Zürich: Herbstferien")
        }
        report = classify(city, ckan)
        assert not report.drifted

    def test_empty_city_export_refuses_to_report_success(self) -> None:
        with pytest.raises(ValueError):
            classify(set(), {entry("2026-10-05", "2026-10-17", "Herbstferien")})


class TestUnicodeNormalisation:
    """NFC vs NFD — `ü` has two encodings, and `Zürich` is in nearly every title."""

    def test_decomposed_umlaut_compares_equal(self) -> None:
        nfc = "Schulen Stadt Zürich: Herbstferien"
        nfd = unicodedata.normalize("NFD", nfc)
        assert nfc != nfd  # the fixture is only meaningful if they differ as bytes
        assert normalise(nfc) == normalise(nfd)

    def test_a_decomposed_export_does_not_drift_wholesale(self) -> None:
        # Without normalisation this reports two drifts in each direction.
        titles = [
            "Schulen Stadt Zürich: Herbstferien",
            "Schulen Stadt Zürich: Sportferien",
        ]
        city = {
            Entry(date(2026, 10, 5), date(2026, 10, 17), normalise(titles[0])),
            Entry(date(2027, 2, 8), date(2027, 2, 20), normalise(titles[1])),
        }
        ckan = {
            Entry(
                date(2026, 10, 5),
                date(2026, 10, 17),
                normalise(unicodedata.normalize("NFD", titles[0])),
            ),
            Entry(
                date(2027, 2, 8),
                date(2027, 2, 20),
                normalise(unicodedata.normalize("NFD", titles[1])),
            ),
        }
        assert not classify(city, ckan).drifted

    def test_the_prefix_still_matches_after_a_decomposed_title_is_normalised(
        self,
    ) -> None:
        # SCHOOL_RECORD_RE contains a literal `ü`; an NFD title would miss it,
        # so every record would silently stop counting as a school record.
        nfd = unicodedata.normalize("NFD", "Schulen Stadt Zürich: Herbstferien")
        assert Entry(date(2026, 10, 5), date(2026, 10, 17), normalise(nfd)).school


class TestSchoolPrefixGate:
    def test_counts_are_reported_per_export(self) -> None:
        # Two school records, not one: a count that happens to equal a
        # hard-coded 1 would pass whether or not anything is counted.
        city = {
            entry("2026-10-05", "2026-10-17", "Schulen Stadt Zürich: Herbstferien"),
            entry("2026-12-19", "2027-01-04", "Schulen Stadt Zürich: Weihnachtsferien"),
            entry("2026-11-01", "2026-11-02", "Allerheiligen"),
        }
        report = classify(city, city)
        assert (report.city_school, report.ckan_school) == (2, 2)

    def test_a_renamed_prefix_agrees_perfectly_and_counts_zero(self) -> None:
        # The exports still match each other, so `drifted` is empty. Only the
        # counts reveal that the marker the feed depends on has gone.
        renamed = {
            entry("2026-10-05", "2026-10-17", "Volksschule Zürich: Herbstferien"),
            entry("2026-12-19", "2027-01-04", "Volksschule Zürich: Weihnachtsferien"),
        }
        report = classify(renamed, renamed)
        assert not report.drifted
        assert (report.city_school, report.ckan_school) == (0, 0)

    def test_ckan_count_is_taken_within_the_window(self) -> None:
        # Records outside the compared span must not prop the count up.
        city = {entry("2026-10-05", "2026-10-17", "Volksschule Zürich: Herbstferien")}
        ckan = city | {
            entry("2018-08-01", "2018-08-18", "Schulen Stadt Zürich: Sommerferien")
        }
        assert classify(city, ckan).ckan_school == 0


class TestParseIcsEdgeCases:
    def test_duration_is_accepted_instead_of_dtend(self) -> None:
        raw = (
            b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
            b"BEGIN:VEVENT\r\nDTSTART;VALUE=DATE:20261005\r\nDURATION:P12D\r\n"
            b"SUMMARY:Herbstferien\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        assert parse_ics(raw) == {entry("2026-10-05", "2026-10-17", "Herbstferien")}

    def test_neither_dtend_nor_duration_is_one_day(self) -> None:
        # RFC 5545 §3.6.1 for a DATE-valued DTSTART.
        raw = (
            b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
            b"BEGIN:VEVENT\r\nDTSTART;VALUE=DATE:20260914\r\n"
            b"SUMMARY:Knabenschiessen\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        assert parse_ics(raw) == {entry("2026-09-14", "2026-09-15", "Knabenschiessen")}

    def test_a_summaryless_event_is_refused_not_skipped(self) -> None:
        # Dropping it would shrink the comparison without saying so.
        raw = (
            b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
            b"BEGIN:VEVENT\r\nDTSTART;VALUE=DATE:20261005\r\nDTEND;VALUE=DATE:20261017\r\n"
            b"END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        with pytest.raises(ValueError):
            parse_ics(raw)


class TestMovedPairing:
    def test_same_title_different_dates_is_reported_as_one_move(self) -> None:
        city = {
            entry("2027-02-08", "2027-02-20", "Schulen Stadt Zürich: Sportferien"),
            entry("2027-04-19", "2027-04-30", "Schulen Stadt Zürich: Frühlingsferien"),
        }
        ckan = {
            entry("2027-02-15", "2027-02-27", "Schulen Stadt Zürich: Sportferien"),
            entry("2027-04-19", "2027-04-30", "Schulen Stadt Zürich: Frühlingsferien"),
        }
        report = classify(city, ckan)
        assert [(a.start, b.start) for a, b in report.moved] == [
            (date(2027, 2, 8), date(2027, 2, 15))
        ]
        # Pairing is presentation only — the move is still drift.
        assert len(report.drifted) == 2

    def test_unrelated_differences_are_not_paired(self) -> None:
        city = {
            entry("2027-02-08", "2027-02-20", "Schulen Stadt Zürich: Sportferien"),
            entry("2027-06-01", "2027-06-02", "Schulen Stadt Zürich: Projekttag"),
        }
        ckan = {
            entry("2027-02-08", "2027-02-20", "Schulen Stadt Zürich: Sportferien"),
            entry("2027-05-03", "2027-05-04", "Schulen Stadt Zürich: Weiterbildung"),
        }
        assert classify(city, ckan).moved == []
