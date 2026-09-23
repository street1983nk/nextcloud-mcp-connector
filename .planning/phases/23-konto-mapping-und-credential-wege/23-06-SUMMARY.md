---
phase: 23-konto-mapping-und-credential-wege
plan: 06
status: complete
subsystem: auth
tags: [token-exchange, binding, enrollment, revocation, standalone, browser-identity, throttle, ui]

requires:
  - phase: 23-konto-mapping-und-credential-wege (23-05)
    provides: "exchange_enroll.begin/complete/settle/abort_enrollment, EXCHANGE_PENDING_CLIENT_ID, ENROLL_PATH als eine Wahrheit, OIDC-Callback-Ruecksprung auf die Enrollment-Seite"
  - phase: 23-konto-mapping-und-credential-wege (23-04)
    provides: "BoundAccounts liest die Bindung je Anfrage ohne Cache, binding_of(principal, client_id)"
  - phase: 23-konto-mapping-und-credential-wege (23-02)
    provides: "EXCHANGE_CLIENT_ID als reservierter Client der fertigen Bindung, Exchange-Konfiguration inklusive azp_allowed"
  - phase: "Browser-Identitaet CR-01 (Bestand)"
    provides: "browser_identity.identifies(request, account_id, flow_id=...) verbraucht den Nachweis genau einmal, pending_step liefert IdentityStep"
  - phase: "Verbindungen und Widerruf (Phase 3/4, Bestand)"
    provides: "provider.end_connection als einziger Widerrufsweg inklusive chain.invalidate, store.form_token/form_token_valid unter PURPOSE_DISCONNECT, connections.py als Vorlage (MAX_FORM_BYTES, bounded_body, form_or_none)"
  - phase: "Layout-Bausteine der Oberflaeche (Bestand)"
    provides: "layout.page/paragraph/detail_list/callout/form/button_primary/button_secondary/external_action/client_name/account_name, errors.error_page"
provides:
  - "exapp/ui/exchange.py (neu): ENROLL_PATH, ACTION_FIELD/ACTION_START/ACTION_REVOKE, AUTH_PARAM/TOKEN_PARAM, RESULT_REVOKED/RESULT_GONE, Binding, invitation_page, handoff_page, waiting_page, identity_page, bound_page"
  - "oauth/exchange_enroll.exchange_routes(env, *, nextcloud, store_provider, browser_identity, end_connection, acting_party, throttle): eine Adresse mit GET und POST, Eigentumspruefung, Widerruf ueber end_connection"
  - "oauth/throttle.py: CLASS_EXCHANGE_ENROLL und CLASS_EXCHANGE_ENROLL_START"
  - "entry_oauth.build_oauth_app: /exchange haengt ausschliesslich im bewaffneten Zustand, innerhalb der BodyLimit-Schleife"
  - "docs/standalone-oauth.md: Abschnitt 'The enrollment page (/exchange)', die Nicht-angehaengt-Liste stimmt wieder"
affects: [24-audit-und-doku]

tech-stack:
  added: []
  patterns:
    - "Eine Adresse, zwei Verben, ein benanntes Aktionsfeld, jeder Zustandswechsel ein POST (die Form von connections_routes), ergaenzt um die Vorgangszustaende von connect.py"
    - "Der Pfad wohnt bei den Formularen, die ihn schreiben (exapp/ui/exchange.py), die Mechanik importiert ihn; die Abhaengigkeit laeuft in eine Richtung"
    - "Zwei Drosselklassen fuer eine Adresse: der startende POST zaehlt jede Anfrage gegen FLOW_LIMIT, die Lesezugriffe zaehlen nur Ablehnungen, weil ein Erfolg einen gezaehlten Versuch zurueckzahlt (WR-03)"
    - "Im Aus-Zustand existiert die Adresse gar nicht statt leer zu antworten: der Werkszustand ist derselbe Aufbau wie vor dem Meilenstein, nicht nur dasselbe Verhalten"
    - "Widerruf ausschliesslich ueber provider.end_connection, nie ueber den Store: nur dieser Weg leert die Caches der Prueferkette"

key-files:
  created:
    - src/mcp_connector/exapp/ui/exchange.py
    - tests/unit/test_oauth_exchange_page.py
  modified:
    - src/mcp_connector/exapp/ui/strings.py
    - src/mcp_connector/oauth/exchange_enroll.py
    - src/mcp_connector/oauth/throttle.py
    - src/mcp_connector/entry_oauth.py
    - tests/unit/test_oauth_exchange_enroll.py
    - tests/unit/test_entry_oauth.py
    - docs/standalone-oauth.md
    - CHANGELOG.md

key-decisions:
  - "Der Widerruf filtert auf EXCHANGE_CLIENT_ID, bevor er end_connection ruft: der Formularwert einer gewoehnlichen Verbindung wird unter demselben Zweck gemuenzt, ohne den Client-Filter koennte der von der ExApp-Connections-Seite gerenderte Wert eine Verbindung ueber eine Oberflaeche beenden, zu der sie nie gehoert hat"
  - "Der Formularwert wird zuerst und in konstanter Zeit geprueft, erst danach wird ueberhaupt etwas gelesen: ein POST, der nie eine gerenderte Seite gesehen hat, loest keinen Store-Zugriff aus"
  - "Der Principal der Eigentumspruefung ist der der Zeile selbst; warum das hier traegt (kein HaRP-Kopf, Nachweis der unabhaengigen Anmeldung ist einmalig, HMAC ueber Zweck und Handle, hoechstens zwei Stundenfenster, nur dem bestaetigten Konto gezeigt) steht als Absatz im Docstring, T-23-29 als accept"
  - "acting_party wird von entry_oauth hereingereicht (', '.join(azp_allowed)), weil nur der Einstiegspunkt die validierte Konfiguration haelt; die Seite behandelt den Wert wie einen Clientnamen aus fremdem Realm"
  - "Jede Abweisung der Seite ist dieselbe Antwort: unbekannter Vorgang, fremdes Konto, bereits widerrufen, fehlender und falscher Formularwert enden auf der Einladung mit demselben ruhigen Hinweis"

requirements-completed: "CRED-02 (abgeschlossen: 23-04 Lesen, 23-05 Entstehung, 23-06 Seite, Anzeige und Widerruf inklusive gemessener Wirkung)"

duration: 3h30m (davon rund 45min Arbeit, zwei Unterbrechungen durch Session-Limits)
completed: 2026-09-23
---

# Phase 23 Plan 06: Anzeige und Widerruf der Exchange-Zuordnung Summary

**Die Browserseite `/exchange`, auf der ein Nutzer im Standalone-Betrieb seine Exchange-Zuordnung einrichtet, mit Datum und handelnder Partei sieht und genau sie widerruft: eine Adresse mit GET und POST und benanntem Aktionsfeld, die Bindung entsteht erst nachdem `browser_identity.identifies` im selben Anfragelauf zugestimmt hat, der Widerruf prueft den HMAC-Formularwert unter `PURPOSE_DISCONNECT` und ruft dann `provider.end_connection` und nie den Store, sodass die Caches der Prueferkette mitgeleert werden; gemessen in einem Test gegen eine Anwendung und ein Token: mit lebender Bindung antwortet `/mcp` mit 200, nach dem Widerruf ueber die Seite antwortet der unmittelbar naechste Aufruf desselben getauschten Tokens 401, ohne Neubau und ohne handgeleerten Cache; im Aus-Zustand existiert die Adresse gar nicht**

## Performance

- **Duration:** rund 45min reine Arbeit, Wanduhr 15:51 bis 19:21 (zwei Unterbrechungen durch Session-Limits)
- **Started:** 2026-09-23T13:51Z
- **Completed:** 2026-09-23T17:21Z
- **Tasks:** 3 (je RED und GREEN einzeln committet, plus ein docs-Commit fuer die Doku-Haelfte von Task 3)
- **Files:** 10 (2 neu, 8 geaendert)

## Accomplishments

- **Die fuenf Seiten des Vorgangs, gebaut wie jede andere Seite dieses Projekts (Task 1).** `exapp/ui/exchange.py` rendert ausschliesslich ueber `layout.page`; roher HTML-Zaehler `<form|<div|<p>` = 0. `invitation_page` nennt in eigenen Worten, was die Erlaubnis ist, wie weit sie reicht und dass sie jederzeit widerrufen werden kann, und traegt genau ein Formular mit `ACTION_START`; `bound_page` zeigt Konto, Anlagedatum (Tag, ausgeschriebener Monat, Jahr, in UTC gerechnet) und handelnde Partei und traegt genau ein Formular mit `ACTION_REVOKE`, verstecktem Handle und verstecktem Formularwert; `waiting_page` aktualisiert sich ueber ein `meta refresh` ohne Ziel, sodass es die Adresse neu laedt, die die Flow-Id ohnehin traegt, und die Id nie im lesbaren Text steht; `handoff_page` ist die einzige Seite, die aus der Anwendung heraus verlinkt; `identity_page` rendert den `IdentityStep` der unabhaengigen Anmeldung. Die handelnde Partei kommt aus fremdem Realm und geht durch `layout.client_name`, ein Test belegt `<script>` gequotet in der Seite. `ENROLL_PATH` steht genau einmal geschrieben, bei den Formularen, die ihn ins Dokument schreiben; `oauth/exchange_enroll.py` importiert ihn (Identitaetstest gruen), und `FLOW_PARAM` ist bewusst der der Zustimmungsoberflaeche, weil der OIDC-Callback von 23-05 genau diesen Namen zurueckschickt.
- **Die Route, die Eigentumspruefung und der bewaffnete Einbau (Task 2).** `exchange_routes` gibt eine Adresse mit GET und POST heraus. Der GET-Zweig ist Einladung, Wartescreen, Identitaetsschritt oder Bindungsseite, je nachdem, was der Vorgang sagt; der POST-Zweig kennt genau zwei Aktionen. **Die Bindung wird nur geschrieben, nachdem `identifies` im selben Anfragelauf `True` gesagt hat** (T-23-26); ist die Antwort `False`, zeigt die Seite `pending_step` und schreibt nichts (eigener Test misst: keine Zeile unter `EXCHANGE_CLIENT_ID` im Store); wirft die Quelle, ist das eine Abweisung und nie ein Durchlassen, woertlich wie `connect._wait` ("a source is a security boundary: its failure is a refusal, never a fallback"). Ein Koerper ueber `MAX_FORM_BYTES` wird an der Ankuendigung und noch einmal an der gelesenen Menge abgewiesen, bevor irgendetwas geparst wird. Zwei Drosselklassen mit begruendetem `#:`-Kommentar: der startende POST zaehlt jede Anfrage gegen `FLOW_LIMIT`, weil er einen Login Flow oeffnet und bei Erfolg 200 antwortet, die Lesezugriffe zaehlen Ablehnungen; sie duerfen sich keine Klasse teilen, weil ein Erfolg einen gezaehlten Versuch zurueckzahlt und ein Neuladen der Einladung sonst die Zaehlung der gerade geoeffneten Flows loeschen wuerde. `entry_oauth` haengt die Routen nur bei `exchange_config is not None` an, innerhalb derselben Schleife, die jede Browserroute in `BodyLimit` wickelt; ein Test belegt, dass `[r.path for r in app.router.routes]` im Aus-Zustand keinen `/exchange`-Eintrag enthaelt.
- **Der Widerruf und die Messung (Task 3).** Der `ACTION_REVOKE`-Zweig prueft `store.form_token_valid(handle, presented, purpose=crypto.PURPOSE_DISCONNECT)` zuerst und in konstanter Zeit, filtert dann auf `EXCHANGE_CLIENT_ID` und nicht widerrufen, und ruft `end_connection(principal_of(row), handle)`; `revoke_authorization`/`revoke_family` kommen im Modul nicht vor (Grep 0). Ein falscher Wert, ein fehlender Wert, ein unbekanntes Handle, das Handle einer gewoehnlichen Verbindung mit ihrem eigenen echten Formularwert und ein bereits widerrufenes Handle sind byte-gleich dieselbe Antwort, und nur der letzte Fall erreicht ueberhaupt den Widerrufsweg (gemessen an den Aufrufen der Attrappe). **Die Messung des Phasen-Erfolgskriteriums 5** steht in `test_the_same_exchanged_token_is_accepted_before_and_refused_after_revocation`: eine gesaete Bindung, ein echtes RS256-signiertes Exchange-Token gegen eine per `respx` bediente JWKS, eine ueber `entry_oauth.build_oauth_app` gebaute Anwendung. Erster `/mcp`-Aufruf 200, Widerruf ueber `POST /exchange`, unmittelbar folgender Aufruf mit demselben Token 401, dazwischen wird nichts neu gebaut und kein Cache von Hand geleert; danach ist `binding_of` None und das App-Passwort ist bei Nextcloud zurueck (die DELETE-Route ist gemockt und wird getroffen).
- **Die Doku sagt wieder die Wahrheit.** Die Liste "What this mode does not attach" war unvollstaendig geworden. `docs/standalone-oauth.md` traegt jetzt den Abschnitt "The enrollment page (`/exchange`)": wozu die Seite da ist, dass sie im Werkszustand gar nicht existiert, dass sie dieselbe unabhaengige Anmeldung verlangt wie die Zustimmung, dass ein Widerruf ueber denselben einen Weg laeuft und sofort wirkt, dass jede Abweisung eine Antwort ist und dass die Connections-Seite weiterhin nicht dazugehoert; ein Satz sagt, dass die ausfuehrliche Einrichtungsdoku ein eigenes Dokument bleibt (EXCH-08, Phase 24). `CHANGELOG.md` traegt denselben Inhalt als einen Absatz unter `[Unreleased] / Added`.

## Task Commits

| Task | Gate | Commit | Inhalt |
|---|---|---|---|
| 1 Seiten | RED | `94c9734` | 14 Tests gegen `exapp/ui/exchange.py` |
| 1 Seiten | GREEN | `b856b19` | `exapp/ui/exchange.py` (291 Zeilen), 17 neue Strings, `ENROLL_PATH`-Umzug |
| 2 Route | RED | `43cdc5e` | 13 Rot-Faelle, Routen- und Einbau-Tests |
| 2 Route | GREEN | `87ab6b6` | `exchange_routes`, 2 Drosselklassen, bewaffneter Einbau |
| 3 Widerruf | RED | `68c23ac` | 3 Rot-Faelle inklusive der Messung |
| 3 Widerruf | GREEN | `c147df3` | `_revoke`, Client-Filter, Principal-Docstring |
| 3 Doku | DOCS | `d02f106` | `docs/standalone-oauth.md`, `CHANGELOG.md` |

### Rot-Beweise

1. **Task 1 (`94c9734`):** `ModuleNotFoundError` auf `mcp_connector.exapp.ui.exchange`, Collection-Abbruch der neuen Datei. (Der Commit-Text dieses einen RED-Commits traegt den Beweis nicht im Koerper, siehe Deviations.)
2. **Task 2 (`43cdc5e`):** 13 failing: `AttributeError: module 'mcp_connector.oauth.exchange_enroll' has no attribute 'exchange_routes'`, die beiden Drosselklassen fehlen, und die bewaffnete Anwendung traegt keine `/exchange`-Adresse. Der Pin, dass die unbewaffnete Anwendung keine solche Adresse hat, war planmaessig von Anfang an gruen: er haelt den Werkszustand fest.
3. **Task 3 (`68c23ac`):** 3 failing, im Fortsetzungslauf unabhaengig gegen den damaligen HEAD reproduziert. Beobachtete Fehlbilder:
   - `test_revoking_over_the_page_runs_over_the_one_revocation_path`: der Widerrufs-POST war eine unbekannte Aktion, Antwort `400` statt der Einladung mit dem "Permission withdrawn"-Hinweis.
   - `test_every_failed_withdrawal_is_one_answer`: `assert 'Already withdrawn' in <Response [400 Bad Request]>.text` schlug fehl, alle fuenf Faelle liefen in denselben 400-Zweig fuer unbekannte Aktionen statt in den ruhigen Hinweis.
   - `test_the_same_exchanged_token_is_accepted_before_and_refused_after_revocation`: `assert 400 == 200` am Widerrufs-POST. Die erste Haelfte der Messung hielt bereits (das getauschte Token erreichte den MCP-Transport mit 200, solange die Bindung lebte), die 401-Haelfte wurde nie erreicht, weil der Widerruf nicht durchging.

## Gate-Zahlen (final bestaetigt nach dem letzten Commit)

- `uv run pytest tests/unit tests/contract`: **4162 passed, 33 skipped, 0 failed** (vor dem Plan 4131: +14 Seiten, +15 Routen und Einbau, +2 Widerruf, +1 Messung, davon 2 Tests in `test_entry_oauth.py`)
- `uv run ruff check .`: All checks passed
- `uv run ruff format --check .`: 263 files already formatted
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: **0 errors, 0 warnings, 0 informations**
- `uv run vulture src scripts vulture_whitelist.py`: still; **kein Whitelist-Eintrag noetig, auch nicht zwischen den Tasks** (alle oeffentlichen Namen in `__all__` und von den Routen gelesen)
- Akzeptanz-Greps: roher HTML-Zaehler in `exchange.py` = 0; `ENROLL_PATH` = `/exchange` und identisch mit dem der Mechanik = `True`; `<script>` gequotet belegt (eigener Test); `exchange_routes` in `entry_oauth.py` = 1, in `entry_exapp.py` = 0; `identifies` im Modul = 3 mit `except` im Umfeld = 2; `end_connection` = 6 und `revoke_authorization|revoke_family` = 0; `PURPOSE_DISCONNECT` = 2 (rendern und pruefen); `/exchange` in `docs/standalone-oauth.md` = 4 (mind. 2); `the connections page` = 1 (mind. 1); Testname mit beiden Haelften vorhanden (`..._accepted_before_and_refused_after_revocation`) mit je einer Zusicherung auf 200 und 401 gegen dieselbe Anwendung und dasselbe Token
- Verifikation 5: `git diff --name-only` ueber den Plan nennt unter `src/` genau `exapp/ui/exchange.py`, `exapp/ui/strings.py`, `oauth/exchange_enroll.py`, `oauth/throttle.py`, `entry_oauth.py`
- Verifikation 6: `git diff pyproject.toml uv.lock` ueber den Plan **leer**
- Verifikation 7: Gedankenstrich- und Emoji-Kontrolle ueber alle 10 geaenderten Dateien und alle 7 Commit-Texte: **0 Treffer**

## Files Created/Modified

- `src/mcp_connector/exapp/ui/exchange.py` (neu, 291 Zeilen) - Moduldocstring mit den drei tragenden Eigenschaften (handelnde Partei ist fremder Text, das Handle steht nie sichtbar, die Flow-Id reist nur in der Adresse), Pfad- und Feldkonstanten, `Binding` als frozene Datenklasse, fuenf Seitenfunktionen, `_result`, `_onwards`, `_meta_refresh`, `_allowed_on`
- `src/mcp_connector/exapp/ui/strings.py` - 17 neue `EXCHANGE_*`-Texte in ruhiger Sprache (wer handelt, wie weit es reicht, jederzeit widerrufbar, Widerruf gilt sofort)
- `src/mcp_connector/oauth/exchange_enroll.py` - der Routenteil: `exchange_routes` mit `enrollment`/`act`/`_act`/`_start`/`_revoke`/`_resume`/`_confirm`/`_bound`, `_is_holding`, `_oversized`, `_store_or_page`, `_generic`, `_page`; der Principal-Absatz als Docstring von `_revoke`
- `src/mcp_connector/oauth/throttle.py` - `CLASS_EXCHANGE_ENROLL`, `CLASS_EXCHANGE_ENROLL_START` samt begruendendem `#:`-Kommentar und `__all__`-Eintraegen
- `src/mcp_connector/entry_oauth.py` - die Routenliste nur im bewaffneten Zustand, `end_connection=provider.end_connection`, `acting_party` aus `azp_allowed`, und der Kommentar, warum die Adresse im Aus-Zustand gar nicht existiert
- `tests/unit/test_oauth_exchange_page.py` (neu, 266 Zeilen, 14 Tests) - jede Seite baut, Formularfelder, Kopfzeilen, Nonce, boesartige handelnde Partei gequotet
- `tests/unit/test_oauth_exchange_enroll.py` - von 20 auf 35 Tests: Routenfaelle mit `TestClient` und Attrappen fuer Login Flow und Browser-Identitaet, die fuenf Widerrufs-Fehlschlaege als eine Antwort, und die Messung mit echter RS256-Signatur gegen eine `respx`-JWKS
- `tests/unit/test_entry_oauth.py` - die Route haengt bewaffnet, und im Aus-Zustand ist sie nicht da
- `docs/standalone-oauth.md` - Abschnitt "The enrollment page (`/exchange`)", plus der Satz, der die Nicht-angehaengt-Liste wieder wahr macht
- `CHANGELOG.md` - ein Absatz unter `[Unreleased] / Added`

## Deviations from Plan

**1. [Rule 3 - blockierend] Rueckgabetyp des Messungs-Helfers auf `Any` gehoben**
- **Found during:** Task 3 GREEN, pyright-Gate
- **Issue:** `post_mcp(...) -> httpx.Response` (aus dem RED-Commit `68c23ac`) liess pyright fehlschlagen: `"httpx2._models.Response" is not assignable to "httpx._models.Response"`. Der Starlette-TestClient antwortet mit dem `httpx2`-Typ, dem Fork, den das MCP-SDK mitbringt, waehrend `respx` im selben Test den gewoehnlichen `httpx`-Typ mockt.
- **Fix:** `-> Any` mit Docstring, der den Grund nennt, exakt das dokumentierte Muster der Datei-Nachbarn (`test_oauth_oidc_routes.py`, `test_oauth_consent_oidc.py`, `test_oauth_abuse.py`)
- **Files modified:** `tests/unit/test_oauth_exchange_enroll.py`
- **Commit:** `c147df3`
- **Verification:** pyright 0 errors; die drei Task-3-Tests unveraendert gruen

**2. [Rule 2 - fehlender Schutz] Der Widerruf filtert auf den Bindungs-Client**
- **Found during:** Task 3 GREEN
- **Issue:** Der Plan verlangt nur die Pruefung des Formularwerts unter `PURPOSE_DISCONNECT`. Denselben Zweck benutzt aber auch die Connections-Seite der ExApp fuer gewoehnliche Verbindungen. Ohne Client-Filter haette ein auf der Connections-Seite gerenderter Formularwert eine gewoehnliche Verbindung ueber `/exchange` beenden koennen, also ueber eine Oberflaeche, zu der sie nie gehoert hat.
- **Fix:** `_revoke` weist jede Zeile ab, deren `client_id` nicht `EXCHANGE_CLIENT_ID` ist (dazu: unbekannt, bereits widerrufen), und faengt sie in derselben einen Antwort ab; der Grund steht im Docstring
- **Files modified:** `src/mcp_connector/oauth/exchange_enroll.py`
- **Commit:** `c147df3`
- **Verification:** `test_every_failed_withdrawal_is_one_answer` legt eine echte gewoehnliche Verbindung mit ihrem echten Formularwert an und belegt, dass sie den Widerrufsweg nie erreicht

**3. [Praezisierung] Das Akzeptanzkriterium zur Drosselklasse misst den Wert statt den Namen**
- **Found during:** Abschluss-Verifikation
- **Issue:** Das Kriterium lautet woertlich `python -c "... print(t.CLASS_EXCHANGE_ENROLL in t.__all__)"` und vergleicht damit den Wert `"exchange-enroll"` gegen eine Liste von Namen; so geschrieben kann es fuer keine Konstante dieses Moduls jemals `True` ergeben
- **Fix:** Die Absicht (die Klasse ist exportiert) ist erfuellt und wurde so gemessen: `"CLASS_EXCHANGE_ENROLL" in t.__all__` und `"CLASS_EXCHANGE_ENROLL_START" in t.__all__` sind beide `True`; keine Codeaenderung
- **Verification:** siehe Gate-Zahlen

**4. [Praezisierung] Die Doku-Haelfte von Task 3 ist ein eigener `docs`-Commit**
- **Found during:** Task 3
- **Issue:** Task 3 buendelt Code, Doku und Changelog. Ein gemeinsamer `feat`-Commit haette den Praefix falsch gesetzt und den Widerrufs-Code mit reiner Prosa vermischt
- **Fix:** `c147df3` traegt den Code, `d02f106` die Doku; beide Gates liefen vor beiden Commits vollstaendig
- **Verification:** beide Commits im Log, volle Suite nach jedem gruen

**5. [Prozess] Zwei Unterbrechungen durch Session-Limits**
- Der Lauf wurde zweimal von Session-Limits unterbrochen. Die erste Unterbrechung fiel zwischen die GREEN-Commits von Task 1 und Task 2 und hinterliess einen sauberen Arbeitsbaum. Die zweite fiel mitten in Task 3 GREEN, unmittelbar nach dem RED-Commit `68c23ac`, und hinterliess eine begonnene, nicht committete Aenderung an `src/mcp_connector/oauth/exchange_enroll.py`.
- **Umgang im Fortsetzungslauf:** auf der begonnenen Aenderung aufgebaut statt neu angesetzt, weil der Diff vollstaendig und konsistent war. Der Rot-Beweis wurde dabei unabhaengig nachgestellt: die Arbeitskopie wurde beiseitegelegt, `git checkout --` stellte den Stand von `68c23ac` her, die drei Tests liefen rot (Fehlbilder oben protokolliert), danach wurde die Arbeitskopie zurueckgelegt und die Gates liefen vollstaendig.
- **Sichtbare Folge:** der RED-Commit von Task 1 (`94c9734`) hat keinen Koerper mit Rot-Beweis, alle anderen haben einen. Nachtraeglich nicht korrigiert, weil ein Rewrite bereits veroeffentlichter Historie teurer ist als diese Notiz.

---

**Total deviations:** 5 (1 Rule-3-Blocker, 1 Rule-2-Schutz auto-ergaenzt, 2 dokumentierte Praezisierungen, 1 Prozessnotiz)
**Impact on plan:** Keine Scope-Ausweitung und kein Architektur-Konflikt. Unter `src/` genau die fuenf geplanten Dateien; `exapp/middleware.py`, `deps.py`, `entry_exapp.py`, `oauth/chain.py`, `oauth/exchange_binding.py`, `oauth/connections.py` und die Mechanik aus 23-05 sind unberuehrt (an 23-05 aenderte nur Task 1 den Import des Pfades). Keine Connections-Seite im Standalone-Betrieb, kein Audit-Eintrag, keine Einrichtungsdoku des Exchange-Pfades. `pyproject.toml` und `uv.lock` byte-identisch, kein Paket installiert.

## Hinweise an den Orchestrator / Folgeplaene

- Phase 23 ist mit diesem Plan inhaltlich geschlossen: CRED-02 traegt Lesen (23-04), Entstehung (23-05) und nun Anzeige und Widerruf inklusive der gemessenen Wirkung.
- Offen und bewusst nach Phase 24 verschoben: Audit-Zeilen fuer Einrichtung und Widerruf (AUDIT-07, T-23-30 als `accept`), und die ausfuehrliche Einrichtungsdoku des Exchange-Pfades (EXCH-08). Der Doku-Abschnitt dieses Plans nennt EXCH-08 ausdruecklich als das Dokument, das noch fehlt.
- Fuer EXCH-08 nutzbar: die Seite heisst dem Nutzer gegenueber "Access for your organization's service", der Vorgang ist Einladung, Nextcloud-Anmeldung, unabhaengige Anmeldung, Bindungsseite; `acting_party` zeigt die konfigurierten `azp_allowed` als Text.
- STATE.md wurde auftragsgemaess nicht angefasst.

## Known Stubs

Keine. Die Seite ist vollstaendig verdrahtet: sie liest echte Store-Zeilen, sie schreibt die Bindung, sie widerruft sie, und die Wirkung des Widerrufs ist an einer echten Anwendung mit einem echten signierten Token gemessen.

## Threat Flags

Keine neue Angriffsflaeche ueber das `<threat_model>` des Plans hinaus. Der Plan haengt genau eine neue Adresse an (`/exchange`, GET und POST), und nur im bewaffneten Zustand; kein Schema, kein neuer Netzpfad (Login Flow v2 und Widerruf laufen ueber die bestehenden `loginflow`- und `provider`-Wege). Disposition wie geplant: T-23-26 mitigiert (`identifies` unmittelbar vor dem einzigen Schreibzugriff, Ausnahme der Quelle ist Abweisung, gemessen), T-23-27 mitigiert (zwei Drosselklassen, startender POST zaehlt jede Anfrage gegen `FLOW_LIMIT`, Fehlerseite E6), T-23-28 mitigiert (fuenf Fehlschlaege byte-gleich eine Antwort, gemessen), T-23-29 `accept` mit dem Begruendungsabsatz im Docstring, T-23-30 `accept` (Audit in Phase 24), T-23-SC: kein Paket installiert, Lock-Diff leer. Zusaetzlich mitigiert (Rule 2, Deviation 2): der Formularwert einer gewoehnlichen Verbindung kann ueber diese Oberflaeche nichts beenden.

## Self-Check: PASSED

- `src/mcp_connector/exapp/ui/exchange.py` FOUND, `tests/unit/test_oauth_exchange_page.py` FOUND, `docs/standalone-oauth.md` FOUND, `CHANGELOG.md` FOUND
- Commits `94c9734`, `b856b19`, `43cdc5e`, `87ab6b6`, `68c23ac`, `c147df3`, `d02f106` FOUND in `git log`
- Volle Suite nach dem letzten Commit erneut gruen (4162 passed, 33 skipped, 0 failed), ruff still, pyright 0 errors, vulture still
