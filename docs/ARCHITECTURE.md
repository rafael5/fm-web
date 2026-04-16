# fm-web — Architecture & Delivery Plan

**Status:** Seed planning document — written before the `fm-web` repo exists.
Once the repo is initialized, this file moves to `fm-web/docs/ARCHITECTURE.md`.

---

## 1. What fm-web is

A read-only, browser-based explorer for FileMan data dictionary, schema, and
entry contents in **any running VistA instance** (Caché/IRIS or YottaDB/GT.M),
accessed entirely through **battle-tested, ship-with-VistA** FileMan and Kernel
RPCs. Zero code is added to the target VistA — no KIDS build, no plugin, no
routine install, no global edit.

## 2. Design principles (non-negotiable)

1. **Portable.** Anything that works against the VEHU YottaDB/Octo image must
   work against an InterSystems IRIS VistA with zero code change. We talk to
   FileMan over the broker; the database engine below FileMan is invisible.
2. **Non-invasive.** We call only RPCs already registered in VistA's standard
   distribution. We do not install routines, do not edit globals, do not
   create options, do not add security keys. Sites grant access by attaching
   an existing read-only menu to a service-account user — normal IRM work.
3. **Leverage FileMan.** FileMan parses its own data dictionary; we do not.
   When a value comes back as external form, it is because `GETS^DIQ` did the
   work. This is the exact lesson the vista-fm-browser B3 bug taught us.
4. **Read-only.** The backend refuses to call any mutating RPC. A hard-coded
   allow-list is enforced at the broker-adapter layer, not just at the UI.
5. **Observable.** Every RPC call is logged with latency, response size, and
   site identifier. Debugging a remote-site issue must not require a rebuild.
6. **Fresh start.** No code imports from vista-fm-browser. Concepts and
   models are reused; code is re-typed with the lessons-learned report as the
   design input.

## 3. High-level architecture

```
┌──────────────────┐        HTTP/JSON        ┌──────────────────────┐
│  React SPA       │ ───────────────────────▶│  FastAPI backend     │
│  (browser)       │ ◀─── session cookie ─── │  (Python 3.12+, uv)  │
│  Vite + TS       │                         │                      │
└──────────────────┘                         │  ┌────────────────┐  │
                                             │  │ RPC adapter    │  │
                                             │  │ (DDR* allow-   │  │
                                             │  │  list enforced)│  │
                                             │  └────────┬───────┘  │
                                             │           │          │
                                             │  ┌────────▼───────┐  │
                                             │  │ XWB NS-mode    │  │
                                             │  │ broker client  │──┼──▶ VistA broker (port 9430)
                                             │  │ (TCP, raw)     │  │    IRIS or YottaDB — same wire
                                             │  └────────────────┘  │
                                             └──────────────────────┘
                                                       │
                                             ┌─────────▼─────────┐
                                             │ frontmatter.db    │  ← read-only, local
                                             │ (phase-2 doc link)│    copy of ~/data/vista-docs
                                             └───────────────────┘
```

No database of our own. No broker-side cache that would drift from the site
DB. All authority lives in the VistA instance being browsed.

## 4. Components

### 4.1 Broker client (`fm_web.broker`)

A hardened fork of the `rpc_broker.py` already proven in vista-fm-browser.
Keeps the XWB NS-mode wire implementation (derived from `XWBPRS.m`/
`XWBTCPMT.m`), adds:

- Connection pooling per (site, UCI) tuple.
- Explicit `read_only=True` flag; `call(rpc_name, …)` rejects any RPC not in
  the allow-list.
- Site-config model: `Site(name, host, port, uci, app_context,
  default_timeout_ms)`.
- Structured exceptions: `BrokerHandshakeError`, `RpcDeniedError`,
  `FileManError` (parsed from `^TMP("DIERR"…)` payloads when present).

**Allow-list (v1):**

| RPC | Wraps | Purpose |
|-----|-------|---------|
| `XUS SIGNON SETUP` | `SIGNON^XUSRB` | Pre-auth intro |
| `XUS AV CODE` | `AVCODE^XUSRB` | Authenticate with ACCESS/VERIFY |
| `XUS GET USER INFO` | `GETUSRINFO^XUSRB4` | Post-auth user metadata (DUZ, name, site) |
| `XUS SIGNOFF` | `SIGNOFF^XUSRB` | Clean disconnect |
| `DDR LISTER` | `LIST^DIC` | List file entries with selected fields |
| `DDR FINDER` | `FIND^DIC` | Search by cross-reference |
| `DDR FIND1` | `FIND1^DIC` | Single-match lookup |
| `DDR GETS ENTRY DATA` | `GETS^DIQ` | Fetch field values by IEN, external form |
| `ORWU DT` | `$$DT^DICRW` | Current FileMan date (env probe) |
| `XWB IM HERE` | keepalive | Session keepalive |

**Removed in phase 1 (see LESSONS-LEARNED L31):** `DDR GET DD` and
`DDR GET DD HASH` were on the initial allow-list but VEHU empirically
returns `"Remote Procedure 'DDR GET DD' doesn't exist on the server."`
for both. They are not universal across VistA distributions. DD browsing
is rebuilt on top of `DDR LISTER` + `DDR GETS ENTRY DATA` against
**file #1 (FILE)** and its FIELD subfile — both use core FileMan
entrypoints (`LIST^DIC`, `GETS^DIQ`) that ship with every site. See §5.

**Deferred to v2:** `XWB GET VARIABLE VALUE` (needed for raw-global tree view
and `$$VFILE^DILFD` cheap counts). Many sites disable it; the v1 UI makes no
assumption it exists.

### 4.2 FileMan service layer (`fm_web.services`)

Pure-Python domain layer. **No database-specific code.** Consumes the broker,
produces typed results.

- `DataDictionaryService` — `list_files(pattern=None, limit, offset)`,
  `get_file(file_number) → FileDef`, `get_field(file, field) → FieldDef`,
  `list_cross_refs(file_number) → list[CrossRefInfo]`.
- `EntryService` — `list_entries(file, fields, start_ien=None, limit, order)`,
  `get_entry(file, ien, fields='*') → Entry` (external form by default).
- `PackageService` — enumerate `^DIC(9.4)` via `DDR LISTER` on file 9.4.
- `SiteService` — current session, UCI, FileMan version, client-side
  DD fingerprint (see §5), server DT.
- `DocLinkService` (phase 2) — SQLite read-only over `frontmatter.db`.

Domain models (Pydantic v2): `FileDef`, `FieldDef`, `TypeSpec`, `Entry`,
`CrossRefInfo`, `PackageDef`, `DocLink`. **These are re-typed from scratch**
referencing vista-fm-browser only as a cross-check, per the clean-break rule.

### 4.3 FastAPI HTTP layer (`fm_web.api`)

Thin. Each route is an adapter from HTTP to a service call.

| Path | Method | Service |
|------|--------|---------|
| `/api/session/signon` | POST | `SiteService.signon(access, verify)` |
| `/api/session/signoff` | POST | `SiteService.signoff` |
| `/api/session/me` | GET | current session info |
| `/api/files` | GET | `DataDictionaryService.list_files` |
| `/api/files/{n}` | GET | `DataDictionaryService.get_file` |
| `/api/files/{n}/fields/{f}` | GET | field attributes |
| `/api/files/{n}/xrefs` | GET | cross-reference list |
| `/api/files/{n}/entries` | GET | paginated entry list |
| `/api/files/{n}/entries/{ien}` | GET | single entry with external values |
| `/api/packages` | GET | list packages |
| `/api/packages/{ien}/files` | GET | files owned by package |
| `/api/docs/for-file/{n}` | GET | phase 2: related VDL docs |
| `/api/docs/for-field/{n}/{f}` | GET | phase 2 (if feasible by keyword join) |
| `/api/health` | GET | no-auth liveness |

**Session model:** server-side Redis-less session. A lightweight signed cookie
carries a session ID; the server holds `{session_id → BrokerConnection}`.
Brokers are kept warm with `XWB IM HERE` every 60s. On idle timeout
(default 15min) the broker connection is closed server-side and the client is
forced to re-sign-on.

### 4.4 React SPA (`frontend/`)

- **Build:** Vite + TypeScript + React 19.
- **State:** TanStack Query for all server state; Zustand for tiny amounts of
  global UI state (active site, theme). No Redux.
- **UI:** shadcn/ui + Tailwind (owned, not a theme you subscribe to).
- **Routing:** TanStack Router (type-safe, file-based).
- **Data tables:** TanStack Table with server-side pagination and column
  resizing — FileMan entry counts reach millions (confirmed: 2.58M in
  EXPRESSIONS); nothing is loaded into memory in bulk.
- **Forms (v1 has one: sign-on):** React Hook Form + Zod.

**Screens (v1):**

1. **Sign-on.** Site dropdown (from config) + ACCESS + VERIFY.
2. **File browser.** Searchable list with name / number / global / package /
   entry-count / field-count columns. Virtualized.
3. **File detail.** Header panel (label, global, package, DD fingerprint) ·
   fields table · cross-refs table · tabs.
4. **Field detail drawer.** Label, type (human-readable decomposition), set
   values, pointer target, help-prompt, description, input transform, last
   edited.
5. **Entry browser.** Per-file, paginated. Column picker drives which fields
   `DDR LISTER` requests. Column types drive renderers (date, pointer, set).
6. **Entry detail.** All fields for one IEN via `DDR GETS ENTRY DATA` with
   `.01;…;9999999` field wildcard resolution done server-side.
7. **Package view.** List packages with file counts; click to see owned files.
8. **Diagnostics.** Current session, RPC call log (last 200), client-side
   DD fingerprint per visited file, FM version, server DT.

**Phase 2 addition:** every file header shows a "Documentation" panel with
links sourced from `frontmatter.db` — doc title, app, patch, URL(s). Every
field detail drawer shows any docs whose title or keyword matches the field
label (best-effort; see §8).

## 5. FileMan RPC call patterns

**List PATIENT entries, first 25, showing .01 and sex:**

```
DDR LISTER
  FILE=2  IENS=""  FIELDS=".01;.02"  FLAGS="P"  NUMBER=25  FROM=""  PART=""
  XREF="B"  SCREEN=""  IDENT=""  TARGET=""
→ IENS + zero-node fragments; JSON-ize and render in the table.
```

**Get one entry with external (resolved) values:**

```
DDR GETS ENTRY DATA
  FILE=2  IENS="1,"  FIELDS=".01;.02;.03;.09;.351"  FLAGS="E"
→ external-format values keyed by field number; external pointer resolution
  is done by FileMan itself (per lesson L12 in LESSONS-LEARNED.md).
```

**Enumerate all FileMan files (via the FILE registry):**

```
DDR LISTER
  FILE=1  IENS=""  FIELDS=".01;.1"  FLAGS="P"  NUMBER=25  XREF="B"
→ one row per file in the system: IEN=file_number, piece 1 = NAME,
  piece 2 = GLOBAL ROOT. Cursor-paginate via FROM=<last_external_value>.
```

**Get a file's header (label + global):**

```
DDR GETS ENTRY DATA
  FILE=1  IENS="<file_number>,"  FIELDS=".01;.1"  FLAGS="E"
→ .01 = NAME, .1 = GLOBAL ROOT. For a deeper read add PACKAGE pointer,
  DESCRIPTION (multiple), etc.
```

**Get a file's field list (via file #1's FIELD subfile):**

```
DDR LISTER
  FILE=1  IENS=",<file_number>,"  FIELDS=".01;1"  FLAGS="P"  NUMBER=200
  XREF="B"
→ one row per field: IEN=field_number, piece 1 = field NAME,
  piece 2 = raw TYPE string (parsed downstream by TypeSpec).
```

**Detect DD drift between sites (fallback — no `DDR GET DD HASH`):**

```
Client-side fingerprint over (file_number, field_number, label, type_raw)
tuples from the above LISTER response:
    h = sha256(sorted(f"{n}|{lbl}|{type_raw}" for each field))[:12]
→ short stable hash; cache per (site, file_number). Equivalent signal
  to a server-computed hash but portable across FileMan distributions
  that don't ship `DDR GET DD HASH`. See LESSONS-LEARNED L31.
```

**Why not `DDR GET DD`?** Empirically absent on the VEHU broker (contract
fixture `tests/contract/fixtures/ddr_get_dd__patient_AL.json` records the
rejection). Using `DDR LISTER` + `DDR GETS ENTRY DATA` on file #1 is more
portable (core FileMan, universally available) and reuses the same parse
pipeline as normal entry browsing.

## 6. Repo structure (`fm-web/`)

```
fm-web/
├── README.md
├── pyproject.toml              # uv-managed; Python 3.12+
├── uv.lock
├── Makefile                    # install, test, test-lf, watch, check, format
├── .envrc                      # direnv: auto-activate .venv
├── docker-compose.yml          # points at local VEHU for dev
├── docs/
│   ├── ARCHITECTURE.md         # this file (moved here on repo init)
│   ├── LESSONS-LEARNED.md      # cross-linked retrospective
│   ├── RPC-SURFACE.md          # detailed spec for every RPC we call
│   └── DEPLOY.md               # packaging + per-site install notes
├── src/fm_web/
│   ├── __init__.py
│   ├── settings.py             # pydantic-settings; env-driven
│   ├── sites.py                # Site config model + loader
│   ├── broker/
│   │   ├── __init__.py
│   │   ├── wire.py             # XWB NS-mode codec (ported from rpc_broker.py)
│   │   ├── client.py           # VistARpcBroker with allow-list
│   │   ├── errors.py
│   │   └── fake.py             # FakeRPCBroker for TDD
│   ├── services/
│   │   ├── data_dictionary.py
│   │   ├── entries.py
│   │   ├── packages.py
│   │   ├── sites.py
│   │   └── doc_links.py        # frontmatter.db reader (phase 2)
│   ├── models/
│   │   ├── file_def.py
│   │   ├── field_def.py
│   │   ├── type_spec.py        # decomposer — re-typed per lessons L4-L9
│   │   ├── entry.py
│   │   ├── cross_ref.py
│   │   ├── package.py
│   │   └── doc_link.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py              # FastAPI factory
│   │   ├── deps.py             # session/broker dependencies
│   │   ├── routes_session.py
│   │   ├── routes_files.py
│   │   ├── routes_entries.py
│   │   ├── routes_packages.py
│   │   ├── routes_docs.py
│   │   └── middleware.py       # rpc-call logger, error handler
│   └── main.py                 # uvicorn entrypoint
├── tests/
│   ├── conftest.py             # FakeRPCBroker + fixtures
│   ├── unit/
│   │   ├── test_wire.py
│   │   ├── test_type_spec.py
│   │   ├── test_data_dictionary.py
│   │   ├── test_entries.py
│   │   └── test_doc_links.py
│   ├── contract/
│   │   └── test_rpc_contracts.py  # FakeRPCBroker contracts
│   └── integration/               # require live VEHU; pytest -m integration
│       ├── test_signon.py
│       ├── test_ddr_lister.py
│       └── test_ddr_gets.py
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx
│   │   ├── app/               # router + layout
│   │   ├── pages/
│   │   │   ├── signon.tsx
│   │   │   ├── files/index.tsx
│   │   │   ├── files/$fileNumber.tsx
│   │   │   ├── entries/$fileNumber.tsx
│   │   │   ├── entries/$fileNumber/$ien.tsx
│   │   │   ├── packages.tsx
│   │   │   └── diagnostics.tsx
│   │   ├── components/
│   │   ├── api/               # TanStack Query hooks wrapping /api/*
│   │   ├── types/             # generated from FastAPI OpenAPI schema
│   │   └── lib/
│   └── tests/                 # vitest + @testing-library/react
└── .github/workflows/
    ├── ci-python.yml
    └── ci-frontend.yml
```

## 7. Tech stack & versions

| Layer | Choice | Why |
|---|---|---|
| Python | 3.12+ | Pattern matching, Self type, TaskGroup |
| Package mgr | uv | Consistent with Rafael's global toolchain |
| Lint / format | ruff | Single tool; project default |
| Type check | mypy (strict) | Lessons learned: type-codes are the source of subtle bugs |
| HTTP | FastAPI | Async for parallel RPC calls; auto OpenAPI schema feeds frontend |
| Models | Pydantic v2 | Frozen, validated domain models |
| Settings | pydantic-settings | 12-factor env-driven config |
| Test | pytest + pytest-asyncio | Existing project convention |
| Frontend framework | React 19 + TypeScript | User request |
| Bundler | Vite | Fast dev; small config |
| Server state | TanStack Query | Caches RPC results; handles pagination |
| Client state | Zustand | Tiny footprint; only UI state |
| Styling | Tailwind + shadcn/ui | Owned components, not a theme subscription |
| Routing | TanStack Router | Type-safe, file-based |
| Tables | TanStack Table | Server-side pagination essential |
| Forms | React Hook Form + Zod | Matches Pydantic on backend |
| Frontend test | Vitest + Testing Library | Standard |
| Types sync | openapi-typescript | Generate TS types from FastAPI schema |

## 8. Phase-2: documentation linking design

Data source: `~/data/vista-docs/state/frontmatter.db` (SQLite, 2,842
documents, **22,022 doc↔file references covering 3,563 distinct file
numbers**). Schema confirmed: `documents`, `doc_file_refs(doc_id,
file_number)`, `doc_keywords`, `doc_security_keys`, `v_file_coverage` view.

### 8.1 File-level linking (high-confidence, v2 launch)

Exact join: given a FileMan file number `n`, query

```sql
SELECT d.doc_id, d.title, d.app_code, d.app_name, d.section, d.pkg_ns,
       d.patch_id, d.pub_date, d.docx_url, d.pdf_url
FROM doc_file_refs r
JOIN documents d USING(doc_id)
WHERE r.file_number = ?
ORDER BY d.app_code, d.patch_id;
```

Delivered as `GET /api/docs/for-file/{n}`. Rendered as a "Documentation"
panel on each file-detail screen.

### 8.2 Field-level linking (best-effort, v2)

No exact field-number table. Approach: case-insensitive substring search over
`doc_keywords` for the field label, intersected with `doc_file_refs` for the
parent file. Mark results as **best-effort** in the UI.

### 8.3 Documentation surface

The VDL inventory at `~/data/vista-docs/inventory/vdl_inventory.csv` adds
companion data (docx↔pdf pairs, decommission dates, doc type). Secondary — the
primary join is through `frontmatter.db` because it carries the file-number
extraction already done by the vista-docs pipeline.

### 8.4 Deployment note

`frontmatter.db` is read-only and ships with the fm-web container as a
mounted volume (or baked image). Regeneration is owned by the vista-docs
pipeline, not fm-web.

## 9. Testing strategy

**Three rings, in order of speed:**

1. **Unit** — pure Python, `FakeRPCBroker` canned responses. Runs in
   milliseconds on host. Covers services, models, wire codec (round-trip
   encode/decode), type-spec decomposition, doc-link queries against a
   fixtures SQLite.
2. **Contract** — recorded RPC responses captured against live VEHU
   (`tests/contract/fixtures/*.json`). Guarantees `FakeRPCBroker` behavior
   matches real broker behavior. Refreshed by a dedicated `make record`
   target that hits VEHU and writes fixtures.
3. **Integration** — hits a running VEHU broker at `localhost:9430` with the
   demo `fakedoc1 / 1Doc!@#$` credentials. Marked `@pytest.mark.integration`;
   excluded from default `make test`, run by `make test-integration`.

**Frontend:** component tests via Vitest + Testing Library; E2E via Playwright
pointed at the FastAPI+React dev server with a recorded RPC layer.

## 10. Deployment / packaging

- **Dev:** `make install && make dev` → FastAPI on `:8000`, React on `:5173`
  via Vite proxy. Requires VEHU running on `localhost:9430`.
- **Single-site deploy:** `docker compose up` — image bundles FastAPI +
  pre-built React static bundle. One config file: `sites.yaml`. `make
  docker-build && make docker-run`.
- **Multi-site (v2+):** same image, `sites.yaml` holds N entries. UI's site
  picker reads `/api/sites`.
- **Credentials:** ACCESS/VERIFY enter through the login screen per session;
  never stored server-side. A per-site `app_context` (e.g. `OR CPRS GUI
  CHART`) is in `sites.yaml`, nothing secret.

## 11. Phased delivery plan

Each phase is a merge-to-main milestone with a runnable product.

| Phase | Scope | Exit criteria |
|-------|-------|---------------|
| **0. Repo bootstrap** | Scaffold, deps, Vite frontend | **DONE** (e38d64c) |
| **1. Broker foundation** | XWB wire codec, allow-list, FakeRPCBroker, VEHU fixtures | **DONE** (1314986 + eb437fa + 71612c4). L31-L35 discovered. |
| **2. Services + API** | DataDictionaryService, EntryService, PackageService; 17 FastAPI routes; session middleware | **DONE** (a2fd616). 174 tests. |
| **3. React skeleton + auth** | Sign-on form, auth gate, file list, diagnostics, Tailwind, TanStack Query, openapi-typescript | **DONE** (b7403fa + f3cffeb). E2E verified against VEHU. L35 resolved (DDR dict params). |
| **4. File browser** | File list page with search + sort; file detail page with fields table + cross-refs | Browser shows all 2,915 files; click through to fields for PATIENT, NEW PERSON, INSTITUTION |
| **5. Entry browser** | Entry list per file with column picker; entry detail drawer | Paginate EXPRESSIONS (2.58M rows) smoothly; external form for dates / pointers / set-of-codes |
| **6. Packages** | Package list + files-by-package view | File 9.4 enumerated; drill-down works |
| **7. V1 hardening** | Error surfacing for FileMan errors (`^TMP("DIERR")`), timeouts, reconnect, audit log | All error paths have UI treatment; 24h soak test passes |
| **8. Docs linking (phase 2)** | `DocLinkService`, `/api/docs/for-file/{n}`, UI "Documentation" panels; best-effort field-level links | File detail for PATIENT shows 505 related VDL docs with links |
| **9. Raw-global view (phase 2+)** | `XWB GET VARIABLE VALUE` backend, tree browser of raw globals, graceful degradation when RPC denied | Browse raw `^DPT` tree; hidden when RPC is denied by the site |
| **10. Multi-site (phase 2+)** | Site picker, per-site session, cross-site DD diff view | Switch between two VEHU instances configured in `sites.yaml` |

## 12. Open design questions (non-blocking)

1. **App context name.** Register `FM BROWSER` (matches current vista-fm-browser
   convention) or something VistA-neutral like `VISTA FILEMAN BROWSER`? The
   broker `TCPConnect` needs this in the handshake.
2. **Session timeout.** 15 min idle is a default; some sites mandate 10 min.
   Make per-site configurable?
3. **Pagination IEN cursor vs offset.** `DDR LISTER`'s `FROM` param is a
   natural IEN cursor — strictly faster than offset on big files but yields a
   non-monotonic page-number UX. Lean: cursor for entries, 1-based pages for
   file list.
4. **Audit logging.** Should the backend write an audit log of every field
   read? Not required for v1 but may be a site demand. Decision deferred.

## 13. What fm-web does NOT do (explicit non-goals)

- No writes of any kind, ever — architectural constraint enforced at the
  broker adapter.
- No KIDS build, no routine install, no option install, no menu edit on the
  target VistA.
- No dependency on YottaDB Python bindings, no `ydb_gbldir`, no MUMPS shell.
- No analysis / reporting pipeline — vista-fm-browser is the ancestor of
  that capability; if analysis is needed later, it will be a separate
  consumer of the `/api/` surface.
- No authentication beyond ACCESS/VERIFY (no SSO, no SAML in v1).
