# Open-Source-Governance einer Schulamt-Organisation auf GitHub

> **Status: Entwurf zur Beratung.** Dieses Dokument ist noch kein Beschluss
> und keine geltende Richtlinie des Schulamts. Es ist die Arbeitsgrundlage für
> den Entscheid, ob und wie das Schulamt eine eigene GitHub-Organisation
> führt. Vor der Gründung sind die offenen Punkte am Ende zu klären.

## 1. Warum überhaupt eine Regelung

Eine GitHub-Organisation ist in zehn Minuten gegründet. Der Aufwand liegt
nicht dort, sondern in dem, was danach unweigerlich eintritt: Nach zwei Jahren
liegen mehrere Repositories da, zwei davon betreut niemand mehr, eines trägt
das Logo des Schulamts und beantwortet seit Monaten keine Meldungen. Ein
verwaistes Repository unter amtlichem Label ist schlechter als gar keines —
es sieht nach einem gepflegten Angebot aus und ist keines.

Diese Regelung soll deshalb genau drei Dinge sicherstellen:

1. Es ist jederzeit klar, **wer** für ein publiziertes Repository zuständig
   ist — auch nach einem Personalwechsel.
2. Es ist vor der Veröffentlichung geprüft, **was** rausgeht.
3. Es ist geregelt, **wie** etwas wieder verschwindet.

## 2. Zweck und Abgrenzung

Die Organisation ist der Publikationsort für Quellcode und technische
Artefakte, die im Schulamt entstehen und öffentlich nachvollziehbar sein
sollen oder dürfen: Werkzeuge, Skripte, Schnittstellen-Komponenten,
Beispielcode, Konfigurationen, Dokumentation zu technischen Lösungen.

Sie ist ausdrücklich **nicht**:

- ein Betriebsort für Dienste mit Publikumserwartung,
- ein Ersatz oder Nebenkanal für `stadt-zuerich.ch`,
- eine Ablage für Daten mit Personenbezug — in keiner Form, auch nicht in
  Testdaten, Beispieldateien oder Commit-Historien,
- der Betriebsort städtischer Fachanwendungen.

### Der Unterschied, an dem sich alles entscheidet

**Code-Heimat ist nicht Dienst-Heimat.** Wo der Quellcode liegt, ist eine
Frage der Nachvollziehbarkeit. Wo ein Dienst betrieben wird, den Eltern,
Schulleitungen oder Lehrpersonen benutzen, ist eine Frage der
Betriebsverantwortung — mit Erreichbarkeit, Support, Barrierefreiheit,
Mehrsprachigkeit und einer Stelle, die haftet, wenn eine Auskunft falsch ist.

Beides in derselben Entscheidung zu behandeln, ist der häufigste Fehler. Ein
Repository in dieser Organisation zu haben, begründet keine Betriebszusage.
Wo ein Dienst tatsächlich für ein Publikum betrieben wird, braucht es einen
eigenen Entscheid und eine benannte betreibende Stelle.

## 3. Einordnung in die Stadt

Vor der Gründung ist mit der Organisation und Informatik Zürich sowie mit Open
Data Zürich zu klären, ob eine städtische Regelung oder ein Dachnamensraum
besteht. Zwei Gründe:

- **Präzedenz.** Statistik Stadt Zürich führt bereits eine eigene
  Organisation. Eine Dienstabteilung mit eigenem Auftritt ist damit kein
  Sonderweg, aber der Entscheid setzt für weitere Dienstabteilungen ein
  Muster und sollte bewusst gefällt werden.
- **Namensraum.** Die Stadt betreibt heute zwei ähnlich benannte
  Organisationen für Open Data. Genau so entsteht Wildwuchs. Name und
  Schreibweise sind deshalb abzustimmen, naheliegende Varianten sind
  mitzuregistrieren.

Der öffentliche Auftritt der Organisation — Name, Logo, Profiltext, Kontakt —
folgt den Vorgaben für den Auftritt der Stadt und wird von Marketing und
Kommunikation verantwortet.

## 4. Rollen und Zugriff

| Rolle | Verantwortung |
|---|---|
| Organisations-Owner | Zugriff, Einstellungen, Aufnahme und Archivierung von Repositories |
| Repository-Maintainer | Fachliche und technische Betreuung eines Repositories, benannt in `CODEOWNERS` |
| Fachliche Verantwortung | Inhaltliche Richtigkeit dessen, was publiziert wird |
| Marketing und Kommunikation | Auftritt, Sprache, Kommunikation nach aussen |

Bindende Regeln zum Zugriff:

- **Mindestens drei Owner**, davon mindestens eine Person ausserhalb der
  Abteilung Marketing und Kommunikation. Zwei sind zu wenig: Ferien und
  Krankheit fallen zusammen.
- Die Organisation hängt an einem **Funktionspostfach** des Schulamts, nie an
  einer persönlichen Adresse — weder privat noch dienstlich personengebunden.
- **Zwei-Faktor-Authentisierung ist für alle Mitglieder verpflichtend** und
  wird organisationsweit erzwungen. Die Wiederherstellungscodes des
  Funktionspostfachs liegen dort, wo sie auch nach einem Austritt jemand
  findet.
- Persönliche Konten sind nie Eigentümer eines Repositories der Organisation.
- **Halbjährlicher Zugriffsreview:** Wer ist Mitglied, wer ist Owner, wer hat
  Schreibrechte, stimmt das noch. Austritte werden am Austrittstag entzogen,
  nicht bei Gelegenheit.

## 5. Was veröffentlicht werden darf

Vor der ersten Veröffentlichung eines Repositories ist Folgendes geprüft und
festgehalten:

1. **Fachliche Freigabe** durch die zuständige Bereichsleitung liegt vor.
2. **Rechte sind geklärt:** Der Code ist im Auftrag des Schulamts entstanden
   oder die Rechte sind eingeräumt. Bei externer Entwicklung ist die
   Veröffentlichung vertraglich gedeckt.
3. **Keine Personendaten** — auch nicht in Beispiel- und Testdaten, auch nicht
   in der Commit-Historie. Historien werden vor der Veröffentlichung geprüft,
   nicht nur der aktuelle Stand.
4. **Keine Zugangsdaten, Schlüssel, internen Hostnamen oder
   Infrastrukturdetails.** Secret Scanning ist aktiviert.
5. **Benannte Betreuung** existiert und ist in `CODEOWNERS` eingetragen.
6. **Die Support-Erwartung ist im README deklariert** — und zwar so, wie sie
   tatsächlich eingelöst wird.

Der Publikationsentscheid liegt bei der Direktion, auf Antrag der fachlich
verantwortlichen Stelle. Marketing und Kommunikation prüft den Auftritt. Der
Antrag ist einseitig (siehe Abschnitt 10); es braucht dafür kein Gremium.

## 6. Mindeststandards je Repository

Jedes Repository führt:

- **README** mit Zweck, Status, Kontakt und — wo zutreffend — dem Hinweis, ob
  es sich um einen offiziellen Dienst des Schulamts handelt oder nicht.
- **Statusangabe** aus drei Möglichkeiten: `aktiv` (wird betreut),
  `experimentell` (ohne Betreuungszusage), `archiviert` (nur noch lesbar).
- **LICENSE.** Standard ist MIT für Code und CC BY 4.0 für Dokumentation.
  Eine Abweichung wird begründet.
- **SECURITY.md** mit einem Meldeweg, der tatsächlich gelesen wird.
- **CONTRIBUTING.md** — oder der ausdrückliche Satz, dass keine Beiträge
  entgegengenommen werden. Beides ist zulässig; Schweigen ist es nicht.
- **CODEOWNERS** mit einem Team der Organisation, nicht mit einer Person.
  Ein Eintrag auf ein nicht existierendes Team wird von GitHub stillschweigend
  ignoriert — dann prüft niemand mehr, und nichts weist darauf hin.
- **Automatische Prüfungen** (Tests, Linting) dort, wo Code ausgeführt wird.
- **Dependabot** aktiviert.

Sprache: Deutsch für alles, was sich an städtische Anspruchsgruppen richtet.
Englisch zusätzlich, wo ein fachliches Publikum ausserhalb der Stadt
angesprochen ist. Schweizer Rechtschreibung.

## 7. Externe Beiträge und Meldungen

- **Deklarierte Reaktionszeiten werden eingehalten.** Lieber «wir antworten
  innert 14 Tagen» und es tun, als eine Zusage, die niemand kennt und niemand
  einlöst.
- **Issues sind kein Support-Kanal für Eltern oder Schulen.** Die regulären
  Kanäle des Schulamts bleiben zuständig; das README sagt das ausdrücklich.
- Beiträge von aussen werden nur übernommen, wenn die Lizenzzustimmung klar
  ist. Bei MIT genügt der Pull Request selbst.
- Wo die Ressourcen für die Betreuung von Beiträgen fehlen, wird das offen
  gesagt und der Beitragskanal geschlossen. Das ist keine Unhöflichkeit,
  sondern die ehrlichere Variante.

## 8. Sicherheit und Datenschutz

- Secret Scanning, Push Protection und Dependabot sind organisationsweit
  aktiviert.
- Die private Schwachstellenmeldung ist je Repository aktiviert und einer
  erreichbaren Adresse zugeordnet.
- Bei einer Meldung: innert fünf Arbeitstagen bestätigen, Tragweite
  einschätzen, die für Informationssicherheit zuständige Stelle der Stadt
  einbeziehen, wenn städtische Systeme betroffen sein könnten.
- Ein versehentlich veröffentlichtes Geheimnis gilt als kompromittiert und
  wird rotiert — Löschen aus der Historie genügt nie.

## 9. KI-Unterstützung bei der Entwicklung

KI-gestützte Entwicklung ist zulässig und wird nicht gesondert
gekennzeichnet — sie ist Werkzeug, nicht Urheberschaft. Daran ändert sich
nichts an der Verantwortung:

- Die publizierende Person verantwortet den Code vollständig, unabhängig
  davon, wie er entstanden ist.
- Nichts wird ungeprüft übernommen. Das gilt besonders für
  Plausibilitätsprüfungen, Sicherheitslogik und alles, was nach aussen wirkt.
- Vertrauliche Inhalte, Personendaten und Zugangsdaten gehören nicht in
  Eingaben an externe KI-Dienste. Es gelten die Vorgaben der Stadt zum
  Einsatz von KI-Werkzeugen.

## 10. Aufnahme eines neuen Projekts

Der Antrag beantwortet fünf Fragen auf einer Seite:

1. Was ist es, und wem nützt es?
2. Warum öffentlich — was ist der Nutzen der Veröffentlichung?
3. Wer betreut es, und wer vertritt diese Person?
4. Was wird nach aussen zugesagt — und was ausdrücklich nicht?
5. Wann wird überprüft, ob es noch gebraucht wird?

Frage 3 und Frage 5 sind die, an denen Anträge scheitern sollen. Wenn sie
sich nicht beantworten lassen, ist das Projekt für eine amtliche
Veröffentlichung noch nicht bereit.

## 11. Lebenszyklus und Archivierung

- **Jährliche Durchsicht** aller Repositories: Betreuung vorhanden, Status
  korrekt, Inhalt noch zutreffend.
- **Ohne Betreuung wird archiviert**, nicht stillgelegt und nicht sich selbst
  überlassen. Ein archiviertes Repository bleibt lesbar und ist als nicht
  mehr betreut erkennbar. Das ist der ehrliche Zustand.
- **Gelöscht wird nur** bei Rechtsverletzung oder versehentlich publizierten
  schützenswerten Daten.
- Wo ein Repository einen benutzten Dienst speist, gilt zusätzlich der
  Abschnitt zur kontrollierten Abschaltung in `docs/BETRIEB.md`: ankündigen,
  Frist geben, bis zuletzt weiterbetreiben.

## 12. Vor der Gründung zu entscheiden

- [ ] Abstimmung mit OIZ und Open Data Zürich: bestehende Regelung, Dachnamensraum, Präzedenz
- [ ] Name und Schreibweise der Organisation, Varianten mitregistrieren
- [ ] Funktionspostfach bestimmen und einrichten
- [ ] Die drei Owner benennen
- [ ] Verhältnis zu Open Data Zürich klären: Was gehört dorthin statt hierher
- [ ] Betriebsaufwand pro Jahr schätzen und der Geschäftsleitung vorlegen
- [ ] Entscheiden, ob der Schulferien-Feed als Dienst hier oder im offiziellen Angebot der Stadt verankert wird
- [ ] Diese Grundlage beschliessen und in einem `.github`-Repository der Organisation veröffentlichen

## Nicht in diesem Dokument geregelt

Beschaffung, Verträge mit externen Entwicklungspartnern, der Betrieb
städtischer Fachanwendungen, und die Frage, welche Daten das Schulamt als Open
Data publiziert. Dafür gelten die bestehenden Regelungen der Stadt.
