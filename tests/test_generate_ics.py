"""Tests for the Zurich school holiday feed generator.

The suite is built around one question: would a well-meaning change break the
feed for a subscribed parent? The exclusive-``end_date`` tests are the reason
this file exists — that convention is easy to "fix" and the damage (every
holiday one day too long, silently) reaches every subscriber overnight.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from icalendar import Calendar

import generate_ics
from generate_ics import (
    HALF_DAY_TITLE,
    SchoolEvent,
    build_calendar,
    clean_title,
    cutoff_date,
    format_period,
    is_school_record,
    keep_dates_together,
    make_uid,
    parse_date,
    parse_stamp,
    render_page,
    render_year_tables,
    sanity_check,
    school_year,
    select_events,
)

CUTOFF = date(2024, 1, 1)
TODAY = date(2026, 8, 23)


def rec(summary: str, start: str, end: str) -> dict:
    """A CKAN record as the datastore actually ships it."""
    return {
        "summary": summary,
        "start_date": f"{start}T00:00:00Z",
        "end_date": f"{end}T00:00:00Z",
    }


def only(events: list[SchoolEvent], summary: str) -> SchoolEvent:
    matches = [e for e in events if e.summary == summary]
    assert len(matches) == 1, f"expected exactly one {summary!r}, got {matches}"
    return matches[0]


# --------------------------------------------------------------------------
# The exclusive end_date convention. Do not relax these.
# --------------------------------------------------------------------------


def test_source_end_date_is_used_verbatim_no_plus_one_correction():
    """Sportferien 2026 run 9–20 February and are stored as 09.02 → 21.02.

    The stored end is already the exclusive iCal end. Adding a day here would
    make every holiday in the feed one day too long.
    """
    events = select_events(
        [rec("Schulen Stadt Zürich: Sportferien", "2026-02-09", "2026-02-21")], CUTOFF
    )

    event = only(events, "Sportferien")
    assert event.start == date(2026, 2, 9)
    assert event.end == date(2026, 2, 21)
    # What a subscriber actually sees as the last day off.
    assert event.end - timedelta(days=1) == date(2026, 2, 20)
    assert (event.end - event.start).days == 12


def test_exclusive_end_survives_into_the_ics_bytes():
    """The guarantee has to hold in the published file, not just in memory."""
    events = select_events(
        [rec("Schulen Stadt Zürich: Sportferien", "2026-02-09", "2026-02-21")], CUTOFF
    )
    ics = build_calendar(events).to_ical().decode("utf-8")

    assert "DTSTART;VALUE=DATE:20260209" in ics
    assert "DTEND;VALUE=DATE:20260221" in ics


def test_single_day_record_with_equal_dates_is_normalised():
    """Some source rows ship end == start instead of an exclusive end."""
    events = select_events(
        [
            rec(
                "Schulen Stadt Zürich schulfrei: Sechseläuten",
                "2026-04-20",
                "2026-04-20",
            )
        ],
        CUTOFF,
    )

    event = only(events, "Sechseläuten")
    assert event.start == date(2026, 4, 20)
    assert event.end == date(2026, 4, 21)


def test_end_before_start_is_rejected():
    with pytest.raises(RuntimeError, match="end < start"):
        select_events(
            [rec("Schulen Stadt Zürich: Kaputt", "2026-02-21", "2026-02-09")], CUTOFF
        )


def test_parse_date_handles_ckan_timestamps():
    assert parse_date("2026-02-09T00:00:00Z") == date(2026, 2, 9)


# --------------------------------------------------------------------------
# A — public holidays are not published
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "summary",
    [
        "Schulen Stadt Zürich: Herbstferien",
        "Schulen Stadt Zürich schulfrei: Knabenschiessen",
    ],
)
def test_school_records_are_recognised(summary):
    assert is_school_record(summary)


@pytest.mark.parametrize(
    "summary",
    [
        "Neujahrstag",
        "Berchtoldstag",
        "Ostersonntag",
        "Nationalfeiertag",
        "Sechseläuten",
    ],
)
def test_public_holidays_are_not_school_records(summary):
    assert not is_school_record(summary)


def test_public_holidays_are_filtered_out_of_the_feed():
    """A December week in the source: one school entry, five holiday duplicates."""
    records = [
        rec("Schulen Stadt Zürich: Weihnachtsferien", "2025-12-20", "2026-01-05"),
        rec("Heilig Abend", "2025-12-24", "2025-12-25"),
        rec("Weihnachten", "2025-12-25", "2025-12-26"),
        rec("Stephanstag", "2025-12-26", "2025-12-27"),
        rec("Silvester", "2025-12-31", "2026-01-01"),
        rec("Neujahrstag", "2026-01-01", "2026-01-02"),
    ]

    events = select_events(records, CUTOFF)

    assert [e.summary for e in events] == ["Weihnachtsferien"]


# --------------------------------------------------------------------------
# B — titles are display strings
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Schulen Stadt Zürich: Herbstferien", "Herbstferien"),
        ("Schulen Stadt Zürich schulfrei: Knabenschiessen", "Knabenschiessen"),
        ("Schulen Stadt Zürich: 1. Schultag", "1. Schultag"),
    ],
)
def test_boilerplate_prefix_is_stripped(raw, expected):
    assert clean_title(raw) == (expected, None)


def test_trailing_parenthetical_moves_into_the_note():
    title, note = clean_title("Schulen Stadt Zürich: Sommerferien (KW 29-33)")

    assert title == "Sommerferien"
    assert note == "KW 29-33"


def test_footnote_asterisk_is_dropped_and_note_kept_verbatim():
    """The longest record in the source, 137 characters, must render short."""
    raw = (
        "Schulen Stadt Zürich schulfrei: Gründonnerstag, Ostern und Frühlingsferien* "
        "(ausnahmsweise KW 16 & 17, weil Ostermontag in der KW 16 ist)"
    )

    title, note = clean_title(raw)

    assert title == "Gründonnerstag, Ostern und Frühlingsferien"
    assert note == "ausnahmsweise KW 16 & 17, weil Ostermontag in der KW 16 ist"
    assert len(title) < len(raw) / 2


def test_kw_spacing_inconsistency_is_normalised():
    """The source ships both '(KW 29-33)' and '(KW29-33)'."""
    assert clean_title("Schulen Stadt Zürich: Sommerferien (KW29-33)")[1] == "KW 29-33"


def test_title_never_becomes_empty():
    """A record that is nothing but the prefix must not vanish into a blank."""
    assert clean_title("Schulen Stadt Zürich:")[0] == "Schulen Stadt Zürich:"


def test_note_reaches_the_ics_as_a_description():
    events = select_events(
        [
            rec(
                "Schulen Stadt Zürich: Sommerferien (KW 29-33)",
                "2026-07-13",
                "2026-08-17",
            )
        ],
        CUTOFF,
    )
    ics = build_calendar(events).to_ical().decode("utf-8")

    assert "SUMMARY:Sommerferien" in ics
    assert "KW 29-33" in ics


def test_events_without_a_note_have_no_description():
    events = select_events(
        [rec("Schulen Stadt Zürich: Herbstferien", "2026-10-05", "2026-10-19")], CUTOFF
    )

    assert only(events, "Herbstferien").description is None


# --------------------------------------------------------------------------
# C — Schulschluss 12 Uhr is a timed event, not a free day
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "Schulen Stadt Zürich schulfrei: Schulschluss um 12 Uhr",
        "Schulen Stadt Zürich schulfrei: Schulschluss 12 Uhr",
        "Schulen Stadt Zürich: Schulschluss um 12 Uhr",
    ],
)
def test_half_day_is_detected_in_every_source_spelling(raw):
    events = select_events([rec(raw, "2026-12-18", "2026-12-19")], CUTOFF)

    assert len(events) == 1
    assert events[0].half_day is True
    assert events[0].summary == HALF_DAY_TITLE


def test_half_day_is_emitted_at_noon_local_time_not_as_all_day():
    events = select_events(
        [
            rec(
                "Schulen Stadt Zürich schulfrei: Schulschluss um 12 Uhr",
                "2026-12-18",
                "2026-12-19",
            )
        ],
        CUTOFF,
    )
    ics = build_calendar(events).to_ical().decode("utf-8")

    assert "DTSTART;TZID=Europe/Zurich:20261218T120000" in ics
    assert "DTEND;TZID=Europe/Zurich:20261218T123000" in ics
    assert "VALUE=DATE:20261218" not in ics


def test_half_day_carries_the_explanation():
    events = select_events(
        [
            rec(
                "Schulen Stadt Zürich schulfrei: Schulschluss um 12 Uhr",
                "2026-12-18",
                "2026-12-19",
            )
        ],
        CUTOFF,
    )

    assert "12 Uhr" in events[0].description


def test_timed_event_ships_its_vtimezone():
    """A TZID reference must resolve inside the same calendar (RFC 5545)."""
    events = select_events(
        [
            rec(
                "Schulen Stadt Zürich schulfrei: Schulschluss um 12 Uhr",
                "2026-12-18",
                "2026-12-19",
            )
        ],
        CUTOFF,
    )
    cal = build_calendar(events)

    assert [c.name for c in cal.walk("VTIMEZONE")] == ["VTIMEZONE"]
    assert cal.walk("VTIMEZONE")[0]["TZID"] == "Europe/Zurich"


def test_all_day_only_feed_ships_no_vtimezone():
    events = select_events(
        [rec("Schulen Stadt Zürich: Herbstferien", "2026-10-05", "2026-10-19")], CUTOFF
    )

    assert build_calendar(events).walk("VTIMEZONE") == []


def test_multi_day_record_is_never_collapsed_into_a_noon_event():
    """Guard: a half-day title on a multi-day span must keep all its days."""
    events = select_events(
        [
            rec(
                "Schulen Stadt Zürich schulfrei: Schulschluss um 12 Uhr",
                "2026-12-18",
                "2026-12-21",
            )
        ],
        CUTOFF,
    )

    assert events[0].half_day is False
    assert events[0].end == date(2026, 12, 21)


# --------------------------------------------------------------------------
# Cutoff
# --------------------------------------------------------------------------


def test_cutoff_is_new_years_day_two_years_back():
    assert cutoff_date(date(2026, 8, 23)) == date(2024, 1, 1)


def test_event_finished_before_the_cutoff_is_dropped():
    assert (
        select_events(
            [rec("Schulen Stadt Zürich: Herbstferien", "2018-10-06", "2018-10-22")],
            CUTOFF,
        )
        == []
    )


def test_event_straddling_the_cutoff_is_kept_in_full():
    """Weihnachtsferien 2023/24 must not be truncated at 1 January."""
    events = select_events(
        [rec("Schulen Stadt Zürich: Weihnachtsferien", "2023-12-25", "2024-01-06")],
        CUTOFF,
    )

    assert only(events, "Weihnachtsferien").start == date(2023, 12, 25)


def test_events_are_sorted_by_start_date():
    records = [
        rec("Schulen Stadt Zürich: Sommerferien", "2026-07-13", "2026-08-17"),
        rec("Schulen Stadt Zürich: Sportferien", "2026-02-09", "2026-02-21"),
        rec("Schulen Stadt Zürich: Herbstferien", "2026-10-05", "2026-10-19"),
    ]

    starts = [e.start for e in select_events(records, CUTOFF)]

    assert starts == sorted(starts)


# --------------------------------------------------------------------------
# UIDs
# --------------------------------------------------------------------------


def test_uid_is_deterministic():
    args = ("Schulen Stadt Zürich: Sportferien", date(2026, 2, 9), date(2026, 2, 21))

    assert make_uid(*args) == make_uid(*args)


def test_uid_is_derived_from_the_raw_summary_so_title_cleanup_does_not_resync():
    """Shortening a title must update subscriptions in place, not re-add them."""
    raw = "Schulen Stadt Zürich: Sportferien"
    events = select_events([rec(raw, "2026-02-09", "2026-02-21")], CUTOFF)

    assert events[0].summary == "Sportferien"
    assert events[0].uid == make_uid(raw, date(2026, 2, 9), date(2026, 2, 21))


def test_different_dates_yield_different_uids():
    a = make_uid(
        "Schulen Stadt Zürich: Sportferien", date(2026, 2, 9), date(2026, 2, 21)
    )
    b = make_uid(
        "Schulen Stadt Zürich: Sportferien", date(2026, 2, 8), date(2026, 2, 21)
    )

    assert a != b


def test_uids_are_unique_across_the_feed():
    records = [
        rec("Schulen Stadt Zürich: Sportferien", "2026-02-09", "2026-02-21"),
        rec("Schulen Stadt Zürich: Herbstferien", "2026-10-05", "2026-10-19"),
        rec("Schulen Stadt Zürich: Sommerferien", "2026-07-13", "2026-08-17"),
    ]

    uids = [e.uid for e in select_events(records, CUTOFF)]

    assert len(set(uids)) == len(uids)


# --------------------------------------------------------------------------
# Calendar envelope
# --------------------------------------------------------------------------


def test_calendar_round_trips_and_keeps_every_event():
    records = [
        rec("Schulen Stadt Zürich: Sportferien", "2026-02-09", "2026-02-21"),
        rec(
            "Schulen Stadt Zürich schulfrei: Schulschluss um 12 Uhr",
            "2026-12-18",
            "2026-12-19",
        ),
        rec("Neujahrstag", "2026-01-01", "2026-01-02"),
    ]
    events = select_events(records, CUTOFF)

    reparsed = Calendar.from_ical(build_calendar(events).to_ical())

    assert len(reparsed.walk("VEVENT")) == len(events) == 2


def test_holidays_never_block_free_busy():
    events = select_events(
        [rec("Schulen Stadt Zürich: Sportferien", "2026-02-09", "2026-02-21")], CUTOFF
    )
    ics = build_calendar(events).to_ical().decode("utf-8")

    assert "TRANSP:TRANSPARENT" in ics


def test_calendar_advertises_a_refresh_interval():
    ics = (
        build_calendar(
            select_events(
                [rec("Schulen Stadt Zürich: Sportferien", "2026-02-09", "2026-02-21")],
                CUTOFF,
            )
        )
        .to_ical()
        .decode("utf-8")
    )

    assert "REFRESH-INTERVAL;VALUE=DURATION:PT24H" in ics
    assert "X-WR-CALNAME:Schulferien Stadt Zürich" in ics


# --------------------------------------------------------------------------
# Sanity gate
# --------------------------------------------------------------------------


def plausible_records(n: int = 60) -> list[dict]:
    """Half school records, half public holidays — the source's real mix."""
    out = []
    for i in range(n // 2):
        year = 2026 + i // 6
        day = date(year, 1, 2) + timedelta(days=i * 3)
        out.append(
            rec(
                "Schulen Stadt Zürich: Ferien",
                day.isoformat(),
                (day + timedelta(days=7)).isoformat(),
            )
        )
        out.append(
            rec("Neujahrstag", day.isoformat(), (day + timedelta(days=1)).isoformat())
        )
    return out


def test_sanity_gate_accepts_a_plausible_feed():
    records = plausible_records()
    events = select_events(records, CUTOFF)
    cal = build_calendar(events)

    sanity_check(records, events, cal.to_ical(), TODAY)  # must not raise


def test_sanity_gate_rejects_a_truncated_fetch():
    records = plausible_records(10)
    events = select_events(records, CUTOFF)

    with pytest.raises(RuntimeError, match="refusing to publish a possibly truncated"):
        sanity_check(records, events, build_calendar(events).to_ical(), TODAY)


def test_sanity_gate_rejects_a_renamed_school_prefix():
    """If the city drops the prefix, fail loudly instead of shipping nothing."""
    records = [
        rec("Volksschule Zürich: Ferien", f"2026-01-{d:02d}", f"2026-01-{d + 1:02d}")
        for d in range(1, 29)
    ] + [rec("Neujahrstag", "2026-01-01", "2026-01-02")] * 12

    with pytest.raises(RuntimeError, match="renamed the school prefix"):
        sanity_check(records, [], b"", TODAY)


def test_sanity_gate_rejects_stale_source_data():
    records = [
        rec("Schulen Stadt Zürich: Ferien", f"2018-01-{d:02d}", f"2018-01-{d + 1:02d}")
        for d in range(1, 29)
    ] * 2

    with pytest.raises(RuntimeError, match="entirely in the past"):
        sanity_check(records, [], b"", TODAY)


def test_sanity_gate_rejects_a_near_empty_feed():
    records = plausible_records()
    events = select_events(records, CUTOFF)[:3]

    with pytest.raises(RuntimeError, match="refusing to publish a near-empty feed"):
        sanity_check(records, events, build_calendar(events).to_ical(), TODAY)


def test_sanity_gate_catches_a_round_trip_mismatch():
    records = plausible_records()
    events = select_events(records, CUTOFF)
    truncated = build_calendar(events[:-1]).to_ical()

    with pytest.raises(RuntimeError, match="Round-trip mismatch"):
        sanity_check(records, events, truncated, TODAY)


# --------------------------------------------------------------------------
# Landing page
# --------------------------------------------------------------------------


def test_page_reports_the_numbers_of_the_run_that_built_it(tmp_path):
    template = tmp_path / "index.html"
    template.write_text(
        "<p>{{EVENT_COUNT}} Termine bis {{RANGE_END}}, Stand {{UPDATED}}</p>",
        encoding="utf-8",
    )
    events = select_events(
        [
            rec("Schulen Stadt Zürich: Sportferien", "2026-02-09", "2026-02-21"),
            rec("Schulen Stadt Zürich: Herbstferien", "2026-10-05", "2026-10-19"),
        ],
        CUTOFF,
    )

    html = render_page(events, date(2026, 8, 23), template)

    # Coverage end is the last day off, not the exclusive iCal end.
    assert html == "<p>2 Termine bis 18.10.2026, Stand 23.08.2026</p>"


def test_unresolved_placeholder_fails_the_build(tmp_path):
    """A page showing a literal {{…}} to parents is worse than no deploy."""
    template = tmp_path / "index.html"
    template.write_text("{{EVENT_COUNT}} und {{UNBEKANNT}}", encoding="utf-8")
    events = select_events(
        [rec("Schulen Stadt Zürich: Sportferien", "2026-02-09", "2026-02-21")], CUTOFF
    )

    with pytest.raises(RuntimeError, match="UNBEKANNT"):
        render_page(events, date(2026, 8, 23), template)


def test_real_landing_page_template_renders():
    """The committed template must stay renderable by the committed code."""
    events = select_events(
        [rec("Schulen Stadt Zürich: Sportferien", "2026-02-09", "2026-02-21")], CUTOFF
    )

    html = render_page(events, date(2026, 8, 23), generate_ics.PAGE_TEMPLATE)

    assert "20.02.2026" in html
    assert "{{" not in html


# --------------------------------------------------------------------------
# Regressions found in review
# --------------------------------------------------------------------------


def test_uid_of_an_equal_dates_record_matches_the_already_published_one():
    """`end == start` rows must hash the *normalised* end, as the feed always did.

    Hashing the raw end instead hands every such record a new UID, so a
    subscriber sees the event removed and re-added. Six rows in the source ship
    this way; they currently predate the cutoff, so the bug is latent until the
    city files the next one inside the window.
    """
    raw = "Schulen Stadt Zürich: Schulschluss 12 Uhr"
    events = select_events([rec(raw, "2026-12-18", "2026-12-18")], CUTOFF)

    assert events[0].uid == make_uid(raw, date(2026, 12, 18), date(2026, 12, 19))


def test_equal_dates_and_exclusive_end_records_agree_on_the_uid():
    """The same day expressed both ways must not produce two different events."""
    equal = select_events(
        [rec("Schulen Stadt Zürich: 1. Schultag", "2026-08-17", "2026-08-17")], CUTOFF
    )
    exclusive = select_events(
        [rec("Schulen Stadt Zürich: 1. Schultag", "2026-08-17", "2026-08-18")], CUTOFF
    )

    assert equal[0].uid == exclusive[0].uid


@pytest.mark.parametrize(
    "raw",
    [
        "Schulen Stadt Zürich schulfrei: Schulschluss um 12.00 Uhr",
        "Schulen Stadt Zürich schulfrei: Schulschluss um 12:00 Uhr",
        "Schulen Stadt Zürich schulfrei: Schulschluss um 12 Uhr für alle Stufen",
    ],
)
def test_reworded_half_day_still_renders_at_noon(raw):
    """A source rewording must not silently turn a school day into a day off."""
    events = select_events([rec(raw, "2026-12-18", "2026-12-19")], CUTOFF)

    assert events[0].half_day is True
    assert events[0].summary == HALF_DAY_TITLE


def test_reworded_half_day_keeps_the_source_wording():
    events = select_events(
        [
            rec(
                "Schulen Stadt Zürich schulfrei: Schulschluss um 12 Uhr für alle Stufen",
                "2026-12-18",
                "2026-12-19",
            )
        ],
        CUTOFF,
    )

    assert "für alle Stufen" in events[0].description


def test_a_different_closing_time_is_not_treated_as_noon():
    events = select_events(
        [
            rec(
                "Schulen Stadt Zürich schulfrei: Schulschluss um 15 Uhr",
                "2026-12-18",
                "2026-12-19",
            )
        ],
        CUTOFF,
    )

    assert events[0].half_day is False


def test_sanity_gate_takes_the_run_date_rather_than_reading_the_clock():
    """`today` is passed in so the staleness gate is testable without patching."""
    records = plausible_records()
    events = select_events(records, CUTOFF)
    ics = build_calendar(events).to_ical()

    sanity_check(records, events, ics, date(2026, 8, 23))
    with pytest.raises(RuntimeError, match="entirely in the past"):
        sanity_check(records, events, ics, date(2099, 1, 1))


# --------------------------------------------------------------------------
# Stable DTSTAMP — identical input must produce identical bytes
# --------------------------------------------------------------------------


def stamped(summary: str, start: str, end: str, created: str | None) -> dict:
    record = rec(summary, start, end)
    if created is not None:
        record["created_date"] = f"{created}T00:00:00Z"
    return record


def test_dtstamp_comes_from_the_source_record_not_the_clock():
    events = select_events(
        [
            stamped(
                "Schulen Stadt Zürich: Sportferien",
                "2026-02-09",
                "2026-02-21",
                "2023-11-13",
            )
        ],
        CUTOFF,
    )
    ics = build_calendar(events).to_ical().decode("utf-8")

    assert "DTSTAMP:20231113T000000Z" in ics


def test_two_runs_produce_byte_identical_output():
    """The nightly rebuild must not rotate the ETag when nothing changed.

    A wall-clock DTSTAMP made every run emit a different file, so every
    subscriber re-downloaded the whole feed each night for no reason.
    """
    records = [
        stamped(
            "Schulen Stadt Zürich: Sportferien",
            "2026-02-09",
            "2026-02-21",
            "2023-11-13",
        ),
        stamped(
            "Schulen Stadt Zürich schulfrei: Schulschluss um 12 Uhr",
            "2026-12-18",
            "2026-12-19",
            "2022-01-04",
        ),
    ]

    first = build_calendar(select_events(records, CUTOFF)).to_ical()
    second = build_calendar(select_events(records, CUTOFF)).to_ical()

    assert first == second
    assert b"DTSTAMP:20231113T000000Z" in first


def test_generated_bytes_carry_no_trace_of_today():
    """Guards against any wall-clock value leaking back into the output."""
    events = select_events(
        [
            stamped(
                "Schulen Stadt Zürich: Sportferien",
                "2026-02-09",
                "2026-02-21",
                "2023-11-13",
            )
        ],
        CUTOFF,
    )
    ics = build_calendar(events).to_ical().decode("utf-8")

    assert date.today().strftime("%Y%m%d") not in ics


def test_missing_created_date_still_yields_a_deterministic_stamp():
    """The fallback is derived from the record, so output stays reproducible."""
    record = stamped(
        "Schulen Stadt Zürich: Sportferien", "2026-02-09", "2026-02-21", None
    )

    assert parse_stamp(record, date(2026, 2, 9)) == parse_stamp(
        record, date(2026, 2, 9)
    )
    assert parse_stamp(record, date(2026, 2, 9)).date() == date(2026, 2, 9)


def test_stamp_is_normalised_to_utc():
    record = rec("Schulen Stadt Zürich: Sportferien", "2026-02-09", "2026-02-21")
    record["created_date"] = "2023-11-13T08:30:00+02:00"

    stamp = parse_stamp(record, date(2026, 2, 9))

    assert stamp.hour == 6 and stamp.tzinfo is not None


# --------------------------------------------------------------------------
# A spelling variant is not extra information
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "Schulen Stadt Zürich schulfrei: Schulschluss um 12 Uhr",
        "Schulen Stadt Zürich schulfrei: Schulschluss um 12.00 Uhr",
        "Schulen Stadt Zürich schulfrei: Schulschluss 12 Uhr",
    ],
)
def test_half_day_spelling_variant_is_not_repeated_in_the_description(raw):
    events = select_events([rec(raw, "2026-12-18", "2026-12-19")], CUTOFF)

    assert events[0].description == "Der Unterricht endet an diesem Tag um 12 Uhr."


# --------------------------------------------------------------------------
# Year overview on the landing page
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 8, 1), 2026),  # first day of the new school year
        (date(2026, 8, 17), 2026),  # 1. Schultag
        (date(2027, 7, 20), 2026),  # summer holidays close the year that ends
        (date(2027, 7, 31), 2026),
        (date(2027, 8, 1), 2027),
    ],
)
def test_school_year_boundary_is_the_first_of_august(day, expected):
    assert school_year(day) == expected


def test_period_of_a_multi_day_holiday_states_the_year_once():
    events = select_events(
        [rec("Schulen Stadt Zürich: Herbstferien", "2026-10-05", "2026-10-17")], CUTOFF
    )

    assert format_period(events[0]) == ("Mo 5.10. – Fr 16.10.2026", "12 Tage")


def test_period_of_a_holiday_crossing_new_year_states_both_years():
    events = select_events(
        [rec("Schulen Stadt Zürich: Weihnachtsferien", "2026-12-21", "2027-01-02")],
        CUTOFF,
    )

    assert format_period(events[0]) == ("Mo 21.12.2026 – Fr 1.1.2027", "12 Tage")


def test_period_of_a_single_day():
    events = select_events(
        [
            rec(
                "Schulen Stadt Zürich schulfrei: Knabenschiessen",
                "2026-09-14",
                "2026-09-15",
            )
        ],
        CUTOFF,
    )

    assert format_period(events[0]) == ("Mo 14.9.2026", "1 Tag")


def test_period_of_a_half_day_is_labelled_as_such():
    events = select_events(
        [
            rec(
                "Schulen Stadt Zürich schulfrei: Schulschluss um 12 Uhr",
                "2026-12-18",
                "2026-12-19",
            )
        ],
        CUTOFF,
    )

    assert format_period(events[0]) == ("Fr 18.12.2026", "halber Tag")


def test_overview_covers_the_current_and_the_next_school_year():
    records = [
        rec("Schulen Stadt Zürich: Herbstferien", "2026-10-05", "2026-10-17"),
        rec("Schulen Stadt Zürich: Herbstferien", "2027-10-11", "2027-10-23"),
        rec("Schulen Stadt Zürich: Herbstferien", "2028-10-09", "2028-10-21"),
    ]

    html_out = render_year_tables(select_events(records, CUTOFF), date(2026, 8, 23))

    assert "Schuljahr 2026/27" in html_out
    assert "Schuljahr 2027/28" in html_out
    assert "Schuljahr 2028/29" not in html_out


def test_overview_lists_events_in_chronological_order():
    records = [
        rec("Schulen Stadt Zürich: Sportferien", "2027-02-15", "2027-02-27"),
        rec("Schulen Stadt Zürich: Herbstferien", "2026-10-05", "2026-10-17"),
        rec("Schulen Stadt Zürich: 1. Schultag", "2026-08-17", "2026-08-18"),
    ]

    html_out = render_year_tables(select_events(records, CUTOFF), date(2026, 8, 23))
    order = [html_out.index(s) for s in ("1. Schultag", "Herbstferien", "Sportferien")]

    assert order == sorted(order)


def test_overview_escapes_titles_and_notes():
    """Titles come from an external source and land in HTML."""
    events = select_events(
        [
            rec(
                "Schulen Stadt Zürich: Ferien <script> (a & b)",
                "2026-10-05",
                "2026-10-17",
            )
        ],
        CUTOFF,
    )

    html_out = render_year_tables(events, date(2026, 8, 23))

    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out
    assert "a &amp; b" in html_out


def test_overview_shows_the_note_as_a_hint():
    events = select_events(
        [
            rec(
                "Schulen Stadt Zürich: Sommerferien (KW 29-33)",
                "2027-07-19",
                "2027-08-21",
            )
        ],
        CUTOFF,
    )

    html_out = render_year_tables(events, date(2026, 8, 23))

    assert 'class="hint">KW 29-33<' in html_out


def test_overview_says_so_rather_than_rendering_nothing():
    events = select_events(
        [rec("Schulen Stadt Zürich: Herbstferien", "2024-10-07", "2024-10-19")], CUTOFF
    )

    assert "keine Termine" in render_year_tables(events, date(2026, 8, 23))


def test_real_template_renders_the_overview():
    """The committed template must actually consume the generated tables."""
    records = [
        rec("Schulen Stadt Zürich: Herbstferien", "2026-10-05", "2026-10-17"),
        rec("Schulen Stadt Zürich: Sportferien", "2027-02-15", "2027-02-27"),
    ]

    page = render_page(
        select_events(records, CUTOFF), date(2026, 8, 23), generate_ics.PAGE_TEMPLATE
    )

    assert "Schuljahr 2026/27" in page
    assert "Mo\u00a05.10. – Fr\u00a016.10.2026" in page
    assert "{{" not in page


def test_dates_stay_atomic_so_a_cell_breaks_only_between_them():
    """On a phone the cell wraps; it must not wrap inside a single date."""
    assert keep_dates_together("Mo 5.10. – Fr 16.10.2026") == (
        "Mo\u00a05.10. – Fr\u00a016.10.2026"
    )


def test_overview_binds_dates_with_a_non_breaking_space():
    events = select_events(
        [rec("Schulen Stadt Zürich: Weihnachtsferien", "2026-12-21", "2027-01-02")],
        CUTOFF,
    )

    html_out = render_year_tables(events, date(2026, 8, 23))

    assert "Mo\u00a021.12.2026 – Fr\u00a01.1.2027" in html_out
    assert "Mo 21.12.2026" not in html_out
