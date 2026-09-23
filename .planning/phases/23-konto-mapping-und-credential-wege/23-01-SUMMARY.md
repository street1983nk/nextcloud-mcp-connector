---
phase: 23-konto-mapping-und-credential-wege
plan: 01
status: complete
subsystem: auth
tags: [token-exchange, identity-mapping, principal, configuration, user-oidc]

requires:
  - phase: 22-konfiguration-kette-und-drosselung (22-01)
    provides: "ExchangeConfig, load_exchange_config, die Helfer _required/_optional/_allowlist, EXCHANGE_VARIABLES"
  - phase: 21-exchange-verifier
    provides: "ExchangeTokenChecker.claims_of als der geprüfte Claim-Satz, den dieser Plan abbildet"
  - phase: "OIDC-Browser-Identität (Bestand)"
    provides: "oidc.user_oidc_unique_uid_sub_v1 als die eine Ableitung der user_oidc-Konto-Id"
provides:
  - "oauth/mapping.py: MAPPING_ACCOUNT_ID_V1, MAPPING_USER_OIDC_SUB_V1, MAPPING_STRATEGIES, MAX_PRINCIPAL_LENGTH, MAX_SUBJECT_LENGTH, MappingSettings, principal_from_claims"
  - "config.py: ENV_EXCHANGE_MAPPING, ENV_EXCHANGE_OIDC_PROVIDER_ID, DEFAULT_EXCHANGE_MAPPING, beide Namen in EXCHANGE_VARIABLES"
  - "oauth/chain.py: ExchangeConfig.mapping als validierte MappingSettings, _provider_id, erweiterter _HINT"
affects: [23-02-identitaet, 23-03-kontoexistenz, 24-audit-und-doku]

tech-stack:
  added: []
  patterns:
    - "Die Abbildungsregel ist eine reine Funktion ohne Umgebung, Netz und Anmeldenamen: der Rückgabeweg kann strukturell nur einen Principal oder None liefern (Pitfall 5)"
    - "Ein Claim-Wert wird geprüft und nie repariert: getrimmt, gekürzt oder normalisiert wäre ein anderes Konto"
    - "Der Konfigurations-Default steht als String in config (config importiert nichts aus oauth); ein Test hält ihn gegen die Konstante des Regelmoduls"
    - "Ein ValueError des Regelmoduls wird an genau einer Stelle zum ToolError übersetzt, der Variablen nennt und Werte nie wiederholt"

key-files:
  created:
    - src/mcp_connector/oauth/mapping.py
    - tests/unit/test_oauth_mapping.py
  modified:
    - src/mcp_connector/config.py
    - src/mcp_connector/oauth/chain.py
    - tests/unit/test_config.py
    - tests/unit/test_oauth_exchange_chain.py

key-decisions:
  - "MAPPING_USER_OIDC_SUB_V1 ist eine Zuweisung von oidc.STRATEGY_USER_OIDC_UNIQUE_UID_SUB_V1 statt eines zweiten Literals: derselbe Name, weil es dieselbe Ableitung ist, und die Zuweisung macht Drift unmöglich"
  - "principal_from_claims weist einen nicht UTF-8-kodierbaren Wert (einsames Surrogat) auf beiden Profilen ab, damit das Nie-Werfen-Versprechen nicht an der Ableitung endet"
  - "Der Mapping-ToolError nennt beide neuen Variablennamen, weil der ValueError des Regelmoduls Felder nennt und ein Feldname im Container-Log auf die App statt auf den zu ändernden Wert zeigt"
  - "_provider_id akzeptiert nur Ziffernfolgen mit Wert > 0 (isdigit + int): kein Vorzeichen, kein Unterstrich-Literal, kein Float"

requirements-completed: "MAP-01 (Teil 1: Abbildungsregel und Konfiguration; Identität und resolve_identity folgen in 23-02)"

duration: 25min
completed: 2026-09-23
---

# Phase 23 Plan 01: Mapping-Profile und Konfiguration Summary

**Das Claim-Mapping des Exchange-Pfades ist freistehende, messbare Mechanik: zwei benannte Profile (Konto-Id unverändert, LDAP-tauglich ohne jede Berührung mit dem Anmeldenamen, und die user_oidc-sub-Ableitung als Aufruf der bestehenden Funktion), genau eine Abbildungsfunktion, die nur einen kanonischen Principal oder None liefern kann und unter keiner Eingabe wirft, dazu NC_MCP_EXCHANGE_MAPPING und NC_MCP_EXCHANGE_OIDC_PROVIDER_ID als Konfiguration mit dokumentiertem Default, deren halber Zustand den Start mit benannter Meldung bricht**

## Performance

- **Duration:** 25 min
- **Started:** 2026-09-23T10:22Z
- **Completed:** 2026-09-23T10:47Z
- **Tasks:** 2 (je RED und GREEN einzeln committet)
- **Files:** 6 (2 neu, 4 geändert), 639 Zeilen hinzu, 12 entfernt

## Accomplishments

- **Zwei Profile, jeder Randfall einzeln gemessen.** `account_id_v1` nimmt den Wert des konfigurierten Claims unverändert als Principal; `user_oidc_unique_uid_sub_v1` ruft `oidc.user_oidc_unique_uid_sub_v1` und baut keine zweite Ableitung (`grep -c "hashlib" src/mcp_connector/oauth/mapping.py` ergibt 0). 86 Testfälle in `test_oauth_mapping.py`.
- **Das Ergebnis ist strukturell der Principal.** `principal_from_claims` kennt keinen Anmeldenamen und hat keinen Rückgabeweg, auf dem einer herauskommen könnte; `grep -v '^\s*#' src/mcp_connector/oauth/mapping.py | grep -c "nc_user\|login_name\|os.environ\|httpx\|await "` ergibt 0, und ein Test hält die Verbote fest.
- **Unbrauchbar heißt nichts, nie eine Ausnahme.** Fehlender Claim, None, Zahl, True, Liste, Wörterbuch, leerer und ungetrimmter String, Steuerzeichen (unter 0x20 und 0x7f), die neun Nextcloud-verbotenen Zeichen und mehr als 64 Zeichen sind je None auf dem Konto-Id-Profil; das sub-Profil prüft den rohen sub nur auf Text, Nicht-Leere, Steuerzeichen und 255 Zeichen, weil sein Ergebnis ein Hash ist. Ein Korpus aus 12 feindlichen Claim-Sätzen mal beide Profile belegt das Nie-Werfen (T-23-03).
- **Halbe Konfiguration bricht den Start benannt.** Unbekannter Profilname, sub-Profil ohne Provider-Id, Provider-Id `abc`/`0`/`-1`/leer, und eine gesetzte Provider-Id neben dem Konto-Id-Profil sind je ein ToolError, der die Variable nennt und den Wert nie wiederholt (T-23-04). Die Regeln stehen nur in `mapping.py`; `chain.py` übersetzt den ValueError an genau einer Stelle.
- **Der Werkszustand ist unverändert.** `load_exchange_config({})` bleibt None; die zwei neuen Namen stehen in `EXCHANGE_VARIABLES`, wodurch der bestehende T-22-02-Parametertest automatisch von 7 auf 9 Fälle wuchs: nur `NC_MCP_EXCHANGE_MAPPING` gesetzt und der Schalter nicht ist eine Startabweisung.
- **Kein Literal-Drift.** `grep -c "NC_MCP_EXCHANGE_MAPPING\|NC_MCP_EXCHANGE_OIDC_PROVIDER_ID" src/mcp_connector/oauth/chain.py` ergibt 0 (nur config-Konstanten); `config.DEFAULT_EXCHANGE_MAPPING == mapping.MAPPING_ACCOUNT_ID_V1` wird von einem Test gehalten, `MAPPING_USER_OIDC_SUB_V1` ist per Zuweisung identisch mit `oidc.STRATEGY_USER_OIDC_UNIQUE_UID_SUB_V1`.
- **Handoff an 23-02 liegt bereit:** `ExchangeConfig.mapping` trägt die validierten `MappingSettings`; noch liest nichts eine Identität daraus (Scope-Fence dieses Plans), der `#:`-Kommentar am Feld sagt das ausdrücklich.

## Task Commits

Jeder Task ist als RED und GREEN getrennt committet:

1. **Task 1: Die Profile und die eine Abbildungsfunktion** - RED `a1bc17a` (Rot-Beweis: `ImportError: cannot import name 'mapping' from 'mcp_connector.oauth'`, Collection-Abbruch), GREEN `8b054f9`
2. **Task 2: Das Profil ist Konfiguration mit dokumentiertem Default** - RED `315193c` (Rot-Beweis: 14 fallende Tests, `AttributeError` auf `config.ENV_EXCHANGE_MAPPING` beziehungsweise `config.DEFAULT_EXCHANGE_MAPPING`), GREEN `5142797`

## Gate-Zahlen (vor jedem GREEN-Commit, final bestätigt)

- `uv run pytest tests/unit tests/contract`: **4015 passed, 33 skipped** (vor dem Plan 3913; +86 Mapping, +14 Konfiguration, +2 automatisch gewachsene T-22-02-Parameter)
- `uv run ruff check .`: All checks passed; `uv run ruff format --check .`: 253 files already formatted
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: 0 errors, 0 warnings, 0 informations
- `uv run vulture src scripts vulture_whitelist.py`: still, Schwelle unverändert
- `git diff --name-only` unter `src/`: genau `oauth/mapping.py`, `oauth/chain.py`, `config.py`; `git diff pyproject.toml uv.lock`: leer (T-23-05)
- Gedankenstrich-Kontrolle über Diff und Commit-Texte: 0 Treffer

## Files Created/Modified

- `src/mcp_connector/oauth/mapping.py` (neu, 157 Zeilen) - Moduldocstring mit den drei Pflichtsätzen (Principal statt Anmeldename mit Verweis auf principal.py, Fracht eines fremden Realms wird geprüft und nie repariert, welches Profil wann), die fünf Konstanten in `__all__`, `MappingSettings` (frozen, slots, Typ vor Wert), `principal_from_claims`
- `src/mcp_connector/config.py` - die zwei `ENV_EXCHANGE_*`-Konstanten mit `#:`-Kommentaren, `DEFAULT_EXCHANGE_MAPPING = "account_id_v1"` mit Begründung (Provider führt die kanonische Kennung; die Annahme, mit der eine Installation ohne F13-Antwort am wenigsten falsch liegt), Namensraum-Kommentar von sieben auf neun fortgeschrieben, beide Namen in `EXCHANGE_VARIABLES`
- `src/mcp_connector/oauth/chain.py` - zwei neue Absätze im Moduldocstring, `_HINT` um beide Variablen erweitert, `ExchangeConfig.mapping` samt umgezogenem `account_claim`-Kommentar (sagt jetzt, wer ihn liest), Leser mit `_optional`-Helfern, `_provider_id`, eigener try-Block für `MappingSettings`
- `tests/unit/test_oauth_mapping.py` (neu, 274 Zeilen) - 86 Fälle: Profile und Grenzen, ValueError-Tabelle, Randfall-Tabelle, verbotene Zeichen parametrisiert, feindlicher Korpus, Strukturverbote
- `tests/unit/test_oauth_exchange_chain.py` - Abschnitt "the mapping profile is configuration with a documented default (MAP-01)", 9 Testfunktionen (12 Fälle), `mapping` im Import
- `tests/unit/test_config.py` - die zwei neuen Namen im Namensraum, Default gegen die Konstante des Mapping-Moduls

## Deviations from Plan

### Dokumentierte Präzisierungen (keine Architektur-Abweichung)

**1. [Präzisierung] `MAPPING_USER_OIDC_SUB_V1` als Zuweisung statt zweitem Literal**
- **Found during:** Task 1 (GREEN)
- **Issue:** Der Plan zeigt `MAPPING_USER_OIDC_SUB_V1 = "user_oidc_unique_uid_sub_v1"` und begründet den Namen damit, dass es dieselbe Ableitung wie `oidc.STRATEGY_USER_OIDC_UNIQUE_UID_SUB_V1` ist
- **Fix:** Die Konstante ist die Zuweisung `= STRATEGY_USER_OIDC_UNIQUE_UID_SUB_V1`; ein Test hält die Gleichheit zusätzlich fest. Gleicher Wert, Drift strukturell unmöglich
- **Verification:** `sorted(MAPPING_STRATEGIES) == ['account_id_v1', 'user_oidc_unique_uid_sub_v1']` (Akzeptanzkriterium) grün

**2. [Rule 2 - fehlende Randfall-Abdeckung] Abweisung nicht kodierbarer Werte (einsames Surrogat)**
- **Found during:** Task 1 (Entwurf der Nie-Werfen-Tests)
- **Issue:** Ein Claim-Wert wie `"\ud800"` ist ein `str`, passiert alle geplanten Prüfungen (kein Steuerzeichen, nicht leer) und ließe `user_oidc_unique_uid_sub_v1` mit `UnicodeEncodeError` fliegen, was das Versprechen "wirft unter keiner Eingabe" bräche (T-23-03)
- **Fix:** `principal_from_claims` prüft auf beiden Profilen `value.encode("utf-8")` und antwortet None auf `UnicodeEncodeError`; zwei Korpusfälle messen es
- **Files modified:** `src/mcp_connector/oauth/mapping.py`, `tests/unit/test_oauth_mapping.py`
- **Verification:** Korpustest über 12 feindliche Claim-Sätze mal beide Profile grün

**3. [Präzisierung] Der Mapping-ToolError nennt beide neuen Variablen**
- **Found during:** Task 2 (GREEN)
- **Issue:** Die Verhaltensliste verlangt Meldungen, die die Variable nennen; der ValueError aus `MappingSettings` nennt aber Felder (`strategy`, `oidc_provider_id`), nicht Variablennamen, und die Regeln sollen nicht zweitgeschrieben werden
- **Fix:** Die Übersetzung im try-Block lautet "The token exchange mapping configured by NC_MCP_EXCHANGE_MAPPING and NC_MCP_EXCHANGE_OIDC_PROVIDER_ID is invalid: {exc}." (beide als config-Konstanten). Damit trägt jede Mapping-Abweisung beide Variablennamen und nie einen Wert; das reine Zahlenformat prüft `_provider_id` vorab mit einer Meldung, die genau die eine Variable nennt
- **Verification:** Die Verhaltens-Tests (unbekannter Name, fehlende Provider-Id, gesetzte Provider-Id beim Konto-Id-Profil) prüfen den jeweiligen Variablennamen in `message` und dass die Werte nicht wiederholt werden

---

**Total deviations:** 3 (1 Rule-2-Randfall auto-ergänzt, 2 dokumentierte Präzisierungen)
**Impact on plan:** Keine Scope-Ausweitung. Unter `src/` genau die drei geplanten Dateien; `oauth/exchange.py`, `oauth/jwks.py`, `oauth/verifier.py`, `exapp/middleware.py`, `deps.py` und die Einstiegspunkte sind unberührt, `pyproject.toml` und `uv.lock` ebenfalls. Kein `email`-Profil, keine Identität, kein Netzaufruf.

## Known Stubs

Keine. `ExchangeConfig.mapping` wird planmäßig noch von nichts ausgewertet (Scope-Fence: `resolve_identity` ist Plan 23-02); das ist im `#:`-Kommentar des Feldes dokumentiert und kein Stub im Sinne einer leeren Zusage.

## Threat Flags

Keine neuen Oberflächen über das `<threat_model>` des Plans hinaus: kein Endpoint, kein Netzpfad, kein Schema. T-23-01 bis T-23-04 sind wie disponiert mitigiert (Tests benannt oben), T-23-05 per leerem Lock-Diff belegt.

## Self-Check: PASSED

- `src/mcp_connector/oauth/mapping.py` FOUND, `tests/unit/test_oauth_mapping.py` FOUND
- Commits `a1bc17a`, `8b054f9`, `315193c`, `5142797` FOUND in `git log`
- Volle Suite nach dem letzten Commit erneut grün (4015 passed, 33 skipped)
