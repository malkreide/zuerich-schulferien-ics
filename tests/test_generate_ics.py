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
    is_school_record,
    make_uid,
    parse_date,
    render_page,
    sanity_check,
    select_events,
)

CUTOFF = date(2024, 1, 1)


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

    sanity_check(records, events, cal.to_ical())  # must not raise


def test_sanity_gate_rejects_a_truncated_fetch():
    records = plausible_records(10)
    events = select_events(records, CUTOFF)

    with pytest.raises(RuntimeError, match="refusing to publish a possibly truncated"):
        sanity_check(records, events, build_calendar(events).to_ical())


def test_sanity_gate_rejects_a_renamed_school_prefix():
    """If the city drops the prefix, fail loudly instead of shipping nothing."""
    records = [
        rec("Volksschule Zürich: Ferien", f"2026-01-{d:02d}", f"2026-01-{d + 1:02d}")
        for d in range(1, 29)
    ] + [rec("Neujahrstag", "2026-01-01", "2026-01-02")] * 12

    with pytest.raises(RuntimeError, match="renamed the school prefix"):
        sanity_check(records, [], b"")


def test_sanity_gate_rejects_stale_source_data():
    records = [
        rec("Schulen Stadt Zürich: Ferien", f"2018-01-{d:02d}", f"2018-01-{d + 1:02d}")
        for d in range(1, 29)
    ] * 2

    with pytest.raises(RuntimeError, match="entirely in the past"):
        sanity_check(records, [], b"")


def test_sanity_gate_rejects_a_near_empty_feed():
    records = plausible_records()
    events = select_events(records, CUTOFF)[:3]

    with pytest.raises(RuntimeError, match="refusing to publish a near-empty feed"):
        sanity_check(records, events, build_calendar(events).to_ical())


def test_sanity_gate_catches_a_round_trip_mismatch():
    records = plausible_records()
    events = select_events(records, CUTOFF)
    truncated = build_calendar(events[:-1]).to_ical()

    with pytest.raises(RuntimeError, match="Round-trip mismatch"):
        sanity_check(records, events, truncated)


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
