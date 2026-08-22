# Zürich Schulferien ICS Feed

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.10+-blue)

> Abonnierbarer iCal-Feed für die Schulferien der Volksschule der Stadt Zürich, generiert aus Open Data Zürich (CKAN)

🇬🇧 [English Version](README.md)

> **Hinweis:** Dies ist ein unabhängiges Open-Source-Projekt und kein
> offizieller Dienst der Stadt Zürich. Datenquelle:
> [Open Data Zürich](https://data.stadt-zuerich.ch/dataset/ssd_schulferien)
> (Datensatz `ssd_schulferien`).

## Übersicht

Die Stadt Zürich publiziert die Schulferien als statische ICS-Dateien pro
Schuljahr, die Nutzerinnen und Nutzer jedes Jahr neu herunterladen und
importieren müssen. Dieses Projekt macht aus den zugrunde liegenden offenen
Daten einen **dauerhaft abonnierbaren** iCalendar-Feed unter einer stabilen
URL: Kalender-Apps fragen ihn automatisch ab, und Änderungen an Ferienterminen
erreichen alle Abonnentinnen und Abonnenten ohne manuelles Zutun.

Ein GitHub-Actions-Workflow ruft den CKAN-Datastore nächtlich ab, generiert
eine RFC-5545-konforme `.ics`-Datei und publiziert sie auf GitHub Pages.

## Abonnieren

Stabile Feed-URL:

```
https://malkreide.github.io/zuerich-schulferien-ics/ferien.ics
```

| Plattform | Abo-Weg |
|---|---|
| Apple Kalender (iOS/macOS), Outlook | `webcal://malkreide.github.io/zuerich-schulferien-ics/ferien.ics` öffnen |
| Google Kalender / Android | `https://calendar.google.com/calendar/r?cid=https://malkreide.github.io/zuerich-schulferien-ics/ferien.ics` öffnen und bestätigen |
| Andere Clients (Nextcloud, Thunderbird, …) | Roh-URL als Kalenderabonnement eintragen |

**Android:** Den HTTPS-Link nicht einfach im Browser antippen — das lädt eine
einmalige statische Kopie herunter, die sich nie aktualisiert. Stattdessen den
Google-Kalender-Link oben verwenden.

## Feed prüfen

Der Feed ist UTF-8 (ohne BOM, CRLF-Zeilenenden). GitHub Pages liefert ihn als
`Content-Type: text/calendar` **ohne** `charset`-Parameter aus — Header lassen
sich dort nicht konfigurieren. Manche Clients raten dann falsch und stellen
Umlaute als Mojibake dar (`ZÃ¼rich` statt `Zürich`). Das betrifft nur die
Anzeige beim Abrufen, nicht die Datei.

Bekannter Fall: **Windows PowerShell 5.1** dekodiert eine Antwort ohne
`charset` als ISO-8859-1. Zum Prüfen deshalb die Kodierung explizit setzen:

```powershell
# Windows PowerShell 5.1 — erzwingt UTF-8
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$r = [Net.WebClient]::new()
$r.Encoding = [Text.Encoding]::UTF8
$r.DownloadString("https://malkreide.github.io/zuerich-schulferien-ics/ferien.ics") -split "`r`n" | Select-Object -First 20
```

PowerShell 7+ (`pwsh`) verwendet standardmässig UTF-8, dort genügt
`Invoke-WebRequest`. Ebenso `curl`:

```bash
curl -s https://malkreide.github.io/zuerich-schulferien-ics/ferien.ics | head -20
```

Kalender-Clients (Apple Kalender, Google Kalender, Thunderbird, Nextcloud)
behandeln iCalendar gemäss RFC 5545 grundsätzlich als UTF-8 und sind von
diesem Verhalten nicht betroffen.

## Funktionen

- Nächtliche automatische Aktualisierung aus der Single Source of Truth (CKAN-Datastore)
- Ganztägige Termine (`VALUE=DATE`) mit korrekt exklusiven Enddaten
- Deterministische SHA-256-UIDs — keine Termin-Duplikate bei Neugenerierung
- `TRANSP:TRANSPARENT` — Ferien blockieren nie die Frei/Gebucht-Anzeige
- Sanity-Gate: unplausible oder unvollständige API-Antworten lassen die
  Pipeline fehlschlagen, statt den letzten guten Feed zu überschreiben
- Keine Server, keine Secrets: GitHub Actions (OIDC) + GitHub Pages

## Wissenswerte Eigenheiten der Daten

- Das CKAN-`end_date` ist **bereits exklusiv** (iCal-Konvention). Die
  Sportferien 2026 dauern vom 9. bis 20. Februar und sind als
  `2026-02-09 → 2026-02-21` gespeichert. Das Skript wendet deshalb **keine**
  `+1 Tag`-Korrektur an — sie würde jeden Ferientermin einen Tag zu lang machen.
- Einzelne eintägige Einträge liefern `end_date == start_date`; diese werden
  zu korrekten Eintages-Terminen normalisiert.
- Die UIDs hashen `(summary, start, end)`. Eine Datumsänderung erscheint in
  den Clients als «alter Termin entfernt, neuer Termin hinzugefügt» statt als
  In-Place-Update. Das ist beabsichtigt: Der Generator bleibt zustandslos.

## Voraussetzungen

- Python 3.10+
- `requests`, `icalendar` (siehe `requirements.txt`)

## Verwendung

```bash
pip install -r requirements.txt
python generate_ics.py    # schreibt public/ferien.ics
```

## Projektstruktur

```
zuerich-schulferien-ics/
├── generate_ics.py           # CKAN abrufen → ICS bauen → Sanity-Gate
├── requirements.txt
├── public/ferien.ics         # generierter Feed (deployt auf GitHub Pages)
└── .github/workflows/deploy.yml  # nächtlicher Cron + manueller Start, OIDC-Deploy
```

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md)

## Mitwirken

Beiträge sind willkommen — siehe [CONTRIBUTING.md](CONTRIBUTING.md).

## Sicherheit

Schwachstellen bitte wie in [SECURITY.md](SECURITY.md) beschrieben melden.

## Lizenz

MIT-Lizenz — siehe [LICENSE](LICENSE)

## Autor

{AUTHOR_LEGAL_NAME} · [malkreide](https://github.com/malkreide)
