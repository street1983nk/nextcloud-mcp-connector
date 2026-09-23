---
phase: quick-260923-bl01
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/unit/test_exapp_env_setup.py
  - appinfo/info.xml
  - docs/n8n-setup.md
  - .planning/BACKLOG.md
  - CHANGELOG.md
autonomous: true
requirements: [BL-01]
must_haves:
  truths:
    - "Keine der drei Store-Beschreibungen in appinfo/info.xml traegt das Wort RAG; der Findling-Satz steht in schlichter Sprache mit Findling-Link in allen drei Sprachen"
    - "Ein neues Text-Gate haelt die Regel (kein RAG-Akronym im Store-Text) fest, damit der naechste Text-Umbau sie nicht wiederentdecken muss; es war gegen den heutigen Text nachweislich rot"
    - "Der n8n-Guide traegt den Retrieval-Schicht-Satz (das Akronym gehoert laut BL-01-Audience-Split genau dorthin)"
    - "Die drei README-Banner sind gegen die BL-01-Anforderungen verifiziert (Wortlaut-Checkliste unten) und bleiben unveraendert, weil sie Owner-abgenommen sind"
    - "BL-01 traegt in .planning/BACKLOG.md einen STATUS-DONE-Block nach dem Muster von BL-15, der nennt, was wo geliefert ist und was ausserhalb dieses Repos liegt"
  artifacts:
    - path: "tests/unit/test_exapp_env_setup.py"
      provides: "test_no_description_carries_the_rag_acronym neben test_no_description_names_a_blocked_mailbox (Zeile ~1896)"
    - path: "appinfo/info.xml"
      provides: "Findling-Satz ohne Akronym an den Zeilen 71 (en), 88 (de), 105 (fr)"
    - path: "docs/n8n-setup.md"
      provides: "Retrieval-Schicht-Satz am Ende des Content-hits-Absatzes (Zeilen 9-13)"
    - path: ".planning/BACKLOG.md"
      provides: "STATUS-Block unter der BL-01-Ueberschrift (Zeile 6)"
  key_links:
    - from: "tests/unit/test_exapp_env_setup.py"
      to: "appinfo/info.xml"
      via: "manifest_root-Fixture, _localised(manifest_root, 'description', lang)"
      pattern: "\\\\bRAG\\\\b"
---

# BL-01: Findling-Synergie-Banner, der Restumfang (Quick)

## Ziel

BL-01 (Owner-Direktive 2026-09-04, "prominently on both sides") abschliessen. Beide
Blocker sind weg: BL-02 (Fidelity-Test) ist seit 07.09. im CI, BL-15 (SEARCH_NOTE plus
Tool-Beschreibung) ist seit heute geschlossen (Commits 9a32764/6ee0a03). Findling ist
als 1.2.0 im Store, die Store-Seite apps.nextcloud.com/apps/findling existiert, die
Tote-Link-Falle aus BL-01 ist damit gegenstandslos.

## Befund: Der Grossteil ist schon geliefert, der Plan schliesst die drei Luecken

Vor dem Schreiben dieses Plans gemessen (Stand HEAD, 0.2.1):

| BL-01-Baustein | Stand | Beleg |
|---|---|---|
| Banner README.md / README.de.md / README.fr.md | GELIEFERT | Commit aed6bdd (PR #3, "the synergy banner (BL-15, BL-01)"); kompakte READMEs Owner-abgenommen 11.09. (74167b5). Banner steht am Kopf: EN Zeilen 9-14, DE 12-17, FR 12-17 |
| Store-Satz in den drei Descriptions | GELIEFERT, ABER MIT AKRONYM | Commit 7ae2249 ("the retrieval layer sentence, 0.1.12"); info.xml Zeilen 71/88/105 sagen "RAG", was der BL-01-Audience-Split ("The store texts of both apps keep their plain language") und die heutige Direktive verbieten. LUECKE 1 |
| Findling-Link im Store-Text | GELIEFERT | Der Link sitzt im Satz selbst. Die "Resources"-Sektion aus BL-01 existiert seit dem Faktenlisten-Umbau 7ae2249 nicht mehr; der Link im Satz erfuellt den Zweck, keine Sektion wiederbeleben |
| n8n-Guide | TEILWEISE | docs/n8n-setup.md Zeilen 9-13 tragen den Content-Hits-Absatz mit Findling-Link und Fidelity-Beweis, aber nicht die Retrieval-Schicht-Formel, die laut Audience-Split genau in Entwickler-Dokumente gehoert. LUECKE 2 |
| docs-site | NICHT IN DIESEM REPO | Es gibt kein docs-site-Artefakt (kein package.json, keine Site-Konfiguration); docs/ sind Markdown-Seiten auf GitHub und tragen den Hinweis bereits. Folgearbeit ausserhalb, siehe unten |
| BACKLOG-Abschluss | OFFEN | BL-01 traegt keinen STATUS-Block. LUECKE 3 |

**Entscheidung zum README-Wortlaut, bewusst und benannt:** Der Auftrag nennt den
englischen BL-01-Entwurf als woertlich zu uebernehmen. Der gelieferte Banner weicht in
zwei Punkten ab, beide zum Besseren: der Halbsatz "and 1.0.0 adds semantic search" fehlt
(waere mit 1.2.0 im Store heute eine falsche Versionsangabe) und der messbare Beweis
(Link auf tests/integration/test_content_hit_fidelity.py) ist eingebaut, was genau die
Permission-Fidelity-Fuehrung ist, die BL-01 verlangt. Diese Fassung ist Owner-abgenommen
(11.09., Commit 74167b5). Regel "bei Owner-Dokumenten nur die erbetenen Aenderungen":
den abgenommenen Text nicht auf einen aelteren Entwurf zurueckdrehen. Die READMEs werden
daher NUR verifiziert, nicht editiert (Checkliste in Task 3). Will der Owner den
Entwurfs-Wortlaut zurueck, ist das ein eigener Auftrag.

## Die gueltigen Banner-Texte (Referenz fuer die Verifikation, kein Edit)

README.md, Zeilen 9-14 (Englisch):

> **Findling + Nextcloud MCP Connector = the retrieval layer for your own RAG.**
> [Findling](https://apps.nextcloud.com/apps/findling) makes the content of your documents
> searchable, scans included. The connector hands those hits to any MCP client, with exactly
> the rights of the asking user; measured in
> [tests/integration/test_content_hit_fidelity.py](tests/integration/test_content_hit_fidelity.py).
> You bring the model, and no content leaves your server.

README.de.md, Zeilen 12-17 (Deutsch, echte Umlaute):

> **Findling + Nextcloud MCP Connector = die Retrieval-Schicht für Ihr eigenes RAG.**
> [Findling](https://apps.nextcloud.com/apps/findling) macht den Inhalt Ihrer Dokumente
> durchsuchbar, Scans eingeschlossen. Der Connector reicht diese Treffer an jeden MCP-Client
> weiter, mit genau den Rechten des fragenden Nutzers; gemessen in
> [tests/integration/test_content_hit_fidelity.py](tests/integration/test_content_hit_fidelity.py).
> Das Modell bringen Sie mit, und kein Inhalt verlässt Ihren Server.

README.fr.md, Zeilen 12-17 (Franzoesisch):

> **Findling + Nextcloud MCP Connector = la couche de récupération de votre propre RAG.**
> [Findling](https://apps.nextcloud.com/apps/findling) rend le contenu de vos documents
> interrogeable, scans compris. Le connecteur transmet ces résultats à tout client MCP, avec
> exactement les droits de l'utilisateur qui demande ; mesuré dans
> [tests/integration/test_content_hit_fidelity.py](tests/integration/test_content_hit_fidelity.py).
> Le modèle, c'est vous qui l'apportez, et aucun contenu ne quitte votre serveur.

Alle drei erfuellen die harten BL-01-Regeln: "retrieval layer for your own RAG" (nie
"this is a RAG system"), Permission-Fidelity als Lead mit messbarem Beweis (BL-02),
lebender Store-Link.

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Store-Gate zuerst, dann der Findling-Satz in schlichter Sprache (Luecke 1)</name>
  <files>tests/unit/test_exapp_env_setup.py, appinfo/info.xml, CHANGELOG.md</files>
  <behavior>
    - Neuer Test test_no_description_carries_the_rag_acronym, direkt neben
      test_no_description_names_a_blocked_mailbox (um Zeile 1896): fuer jede Sprache in
      MANIFEST_LANGS die Description via _localised holen und
      re.search(r"\bRAG\b", description) is None asserten. WICHTIG: case-sensitiv und mit
      Wortgrenzen, denn der Substring "rag" steckt in "storage", "fragenden" und
      "interrogeable"; genau deshalb NICHT casefolden. re ist im Modul schon importiert
      (ENTERPRISE_HEADING). Docstring nennt den Grund: BL-01-Audience-Split, das Akronym
      gehoert in READMEs und Entwickler-Dokumente, der Store spricht schlichte Sprache.
    - ROT-Beweis: Der Test MUSS gegen den heutigen Text an allen drei Stellen fallen
      (Zeilen 71, 88, 105 tragen "RAG"). Ohne Rot-Lauf kein Fix-Commit.
  </behavior>
  <action>
    Danach in appinfo/info.xml die drei Findling-Saetze ersetzen (Absatzposition
    unveraendert: eigener Absatz nach den Bullets, vor "### Enterprise"; Leerzeilen davor
    und danach bleiben, weil das Paragraph-Gate Einzelzeilenumbrueche verbietet):

    Zeile 71 (en) neu:
    "Together with [Findling](https://apps.nextcloud.com/apps/findling), search hits include the contents of your documents, scans included, with exactly the rights of the asking user."

    Zeile 88 (de) neu:
    "Zusammen mit [Findling](https://apps.nextcloud.com/apps/findling) enthalten Suchtreffer die Inhalte Ihrer Dokumente, auch aus Scans, mit genau den Rechten des fragenden Nutzers."

    Zeile 105 (fr) neu:
    "Avec [Findling](https://apps.nextcloud.com/apps/findling), les résultats de recherche incluent le contenu de vos documents, numérisations comprises, avec exactement les droits de l'utilisateur qui demande."

    Genau EIN Satz je Sprache, Link inline (die alte "Resources"-Sektion aus BL-01
    existiert nicht mehr, nichts wiederbeleben). Keine Backticks, keine Tabelle, kein
    HTML, kein Bild, keine Linie, kein Em- oder En-Dash, kein Emoji, und keiner der
    Saetze traegt den Substring "archiv" (FORBIDDEN_VOCABULARY, Gate prueft
    case-insensitiv als Substring). Die FAQ-Marker (background/switch/disconnect/read
    only und ihre DE/FR-Pendants) stehen in den Bullets und bleiben unberuehrt; die
    Enterprise-Sektionen (Markergate an sechs Stellen) liegen UNTER dem Satz und werden
    nicht angefasst.

    CHANGELOG.md, Sektion [Unreleased], Unterpunkt "Changed" (anlegen, falls nicht
    vorhanden), ein Eintrag auf Englisch sinngemaess: "The Findling sentence of the three
    store descriptions speaks plain language and no longer carries the acronym; the store
    page shows it with the next release." Kein "archiv"-Substring, keine Dashes.

    ANMERKUNG, die in den Commit-Text gehoert: Der Store rendert die Description des
    HOCHGELADENEN Releases. Der korrigierte Text reist erst mit dem NAECHSTEN Release
    mit; das ist gewollt, dieser Plan loest KEIN Release aus.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/test_exapp_env_setup.py -x -q</automated>
  </verify>
  <done>Neues Gate war rot gegen den alten Text (Rot-Lauf dokumentiert), ist gruen gegen den neuen; alle bestehenden Gates der Datei gruen; drei Descriptions ohne RAG, mit Findling-Link, ein Satz je Sprache; CHANGELOG-Eintrag steht.</done>
</task>

<task type="auto">
  <name>Task 2: Retrieval-Schicht-Satz im n8n-Guide (Luecke 2)</name>
  <files>docs/n8n-setup.md</files>
  <action>
    Den bestehenden Absatz "Content hits included:" (Zeilen 9-13, Englisch) um einen
    Schlusssatz ergaenzen, nach dem Proof-Link, im selben Absatz:

    "Together they are the retrieval layer for your own RAG: you bring the model, and no content leaves your server."

    Nichts sonst am Guide aendern (er ist ein Messprotokoll, die Versionszeilen 16-21
    sind datierte Evidenz und bleiben). Der Guide ist ein Entwickler-Dokument, das
    Akronym gehoert laut BL-01-Audience-Split genau hierhin. docs/ liegt nicht im
    PUBLIC_MARKDOWN-Vokabular-Gate, trotzdem gelten die Projektregeln: keine Dashes,
    keine Emojis, kein "archiv". Formel "retrieval layer for your own RAG", NIEMALS
    "this is a RAG system".
  </action>
  <verify>
    <automated>grep -c "retrieval layer for your own RAG" docs/n8n-setup.md</automated>
  </verify>
  <done>Der Absatz Zeilen 9-14 traegt Findling-Link, Fidelity-Beweis und die Retrieval-Schicht-Formel; grep liefert genau 1.</done>
</task>

<task type="auto">
  <name>Task 3: README-Verifikation ohne Edit, BL-01 im BACKLOG schliessen (Luecke 3)</name>
  <files>.planning/BACKLOG.md</files>
  <action>
    Erst die README-Checkliste fahren (NUR lesen, kein Edit; bei einem Fehlschlag
    anhalten und berichten statt eigenmaechtig zu texten):
    - je Datei genau ein Banner-Block am Kopf (README.md 9-14, README.de.md 12-17,
      README.fr.md 12-17), Wortlaut wie im Referenzblock dieses Plans
    - "retrieval layer" / "Retrieval-Schicht" / "couche de récupération" vorhanden,
      String "RAG system" in keiner Datei
    - Link https://apps.nextcloud.com/apps/findling vorhanden (Seite existiert,
      Findling 1.2.0 ist im Store)
    - Link auf tests/integration/test_content_hit_fidelity.py vorhanden (der messbare
      Permission-Fidelity-Lead)

    Dann in .planning/BACKLOG.md unter der BL-01-Ueberschrift (Zeile 6) einen
    STATUS-Block nach dem Muster von BL-15 (Zeile 575) einfuegen, deutsch, sinngemaess:

    "**STATUS 2026-09-23: DONE.** Banner in allen drei READMEs seit aed6bdd (PR #3,
    0.1.12), kompakte Fassung Owner-abgenommen 11.09. (74167b5), mit Fidelity-Beweis
    statt der Versionszeile des Entwurfs. Store-Satz seit 7ae2249; mit diesem Quick-Fix
    in schlichter Sprache ohne das Akronym (BL-01-Audience-Split), gehalten von einem
    Gate in tests/unit/test_exapp_env_setup.py, reist mit dem naechsten Release.
    n8n-Guide traegt Content-Hits-Absatz plus Retrieval-Schicht-Satz. Die
    Resources-Sektion aus diesem Eintrag existiert seit dem Faktenlisten-Umbau nicht
    mehr, der Link sitzt im Satz. Ausserhalb dieses Repos: die Spiegelung auf der
    Findling-Seite (deren BL-F01) und eine docs-site, die es in diesem Repo nicht gibt.
    Tote-Link-Falle gegenstandslos, Findling 1.2.0 ist im Store."

    Keine Em- oder En-Dashes, echte Umlaute.
  </action>
  <verify>
    <automated>grep -c "STATUS 2026-09-23: DONE" .planning/BACKLOG.md</automated>
  </verify>
  <done>Checkliste komplett gruen (sonst Stopp mit Bericht); BL-01 traegt den STATUS-Block; grep liefert mindestens 1 unter der BL-01-Ueberschrift.</done>
</task>

</tasks>

## Betroffene Text-Gates und warum sie gruen bleiben

| Gate | Datei | Beruehrung | Warum gruen |
|---|---|---|---|
| test_the_enterprise_paragraph_carries_its_markers_at_all_six_places | test_exapp_env_setup.py:2518 | KEINE | Der Findling-Satz liegt VOR "### Enterprise"; die sechs Enterprise-Sektionen (3 READMEs, 3 Descriptions) werden nicht angefasst. Buchstabengetreue Marker unberuehrt |
| description_problems (Backtick, Tabelle, HTML, Bild, Linie, Absatz-Leerzeilen, Summary-Laenge, "archiv") | test_exapp_env_setup.py:1866 | Ja (neue Saetze) | Neue Saetze: reine Prosa mit einem Markdown-Link, Absatzstruktur unveraendert, kein "archiv"-Substring in EN/DE/FR |
| test_every_description_carries_the_answer_of_the_faq | test_exapp_env_setup.py:1871 | KEINE | Die Marker (background/Hintergrund/arrière-plan, switch/Schalter/interrupteur, disconnect/trenn/déconnect, read only/nur lesen/lecture seule) stehen in den Bullets, die bleiben |
| test_no_description_names_a_blocked_mailbox | test_exapp_env_setup.py:1896 | KEINE | Keine Ordnernamen in den neuen Saetzen |
| Vokabular-Gate ueber PUBLIC_MARKDOWN (READMEs, CHANGELOG) | test_exapp_env_setup.py:2005 | Ja (CHANGELOG-Eintrag) | Eintrag ohne "archiv"-Substring formulieren |
| Em-Dash/Emoji-Gate | test_exapp_admin_settings.py:732 | KEINE | Deckt nur UI-Strings ab; die Projektregel gilt trotzdem fuer alle neuen Texte |
| Enterprise-Wortlisten-Test (zweiter, ab Zeile 2562) | test_exapp_env_setup.py | KEINE | Liest nur die Enterprise-Sektionen |
| NEU: test_no_description_carries_the_rag_acronym | test_exapp_env_setup.py (Task 1) | Wird angelegt | Test-first, Rot-Beweis gegen den heutigen Text Pflicht |

## Commit-Aufteilung

1. `test(store): Gate gegen das RAG-Akronym in den drei Store-Beschreibungen (BL-01)`
   nur tests/unit/test_exapp_env_setup.py; im Commit-Text den Rot-Beweis nennen
   (faellt an Zeile 71/88/105 des alten Texts).
2. `docs(store): der Findling-Satz in schlichter Sprache, in allen drei Sprachen (BL-01)`
   appinfo/info.xml plus CHANGELOG.md; Anmerkung im Commit-Text: reist erst mit dem
   naechsten Release, dieser Fix loest keines aus.
3. `docs(n8n): der Retrieval-Schicht-Satz im Guide, BL-01 geschlossen`
   docs/n8n-setup.md plus .planning/BACKLOG.md.

## Abschlussverifikation

```
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright
uv run vulture
```

Alle fuenf gruen VOR dem letzten Commit (Projektregel Python-Qualitaetsgates; pyright
immer mit erzwungener CI-Version).

## Ausserhalb dieses Repos (Folgearbeit, hier nur notiert)

- **Findling-Seite (BL-F01 im Findling-Repo):** Spiegel-Banner und Store-Schluss-Satz
  auf der Findling-Seite; deren Store-Text ist durch Findling-D-12 gegated.
- **docs-site:** existiert in diesem Repo nicht (docs/ sind GitHub-Markdown-Seiten und
  tragen den Hinweis nach diesem Plan). Sollte je eine eigene Doku-Site entstehen,
  gehoert der Banner dorthin.
- **Naechstes Release:** traegt den korrigierten Store-Text in den Store. Kein Release
  ohne Owner (Projektregel); dieser Plan stoesst keines an.

## Erfolgskriterien

- BL-01 traegt STATUS DONE, mit Beleg je Baustein
- Drei Store-Descriptions: ein Findling-Satz in schlichter Sprache, mit Link, ohne RAG
- Neues Gate haelt die Regel und war nachweislich rot gegen den alten Text
- n8n-Guide traegt die Retrieval-Schicht-Formel
- READMEs unveraendert und gegen die Checkliste verifiziert
- Volle Suite, ruff check, ruff format, pyright, vulture gruen
