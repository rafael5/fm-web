# Claude Project Context — fm-web

## What this project is
A read-only, browser-based explorer for VistA FileMan data dictionary,
schema, and entry contents, accessed entirely through ship-with-VistA
FileMan and Kernel RPCs (`DDR LISTER`, `DDR GETS ENTRY DATA`, etc.) over
the XWB broker. Portable across YottaDB/GT.M and Caché/IRIS — zero code
added to the target VistA, no KIDS build, no routine install. Succeeds
[vista-fm-browser](https://github.com/rafael5/vista-fm-browser) (archived
as proof-of-concept); clean-sheet rewrite in its own repo.

Stack: FastAPI backend + React 19/TypeScript/Vite SPA.

## Start every session by reading
1. `docs/ARCHITECTURE.md` — delivery plan, RPC allow-list, tech stack
2. `docs/LESSONS-LEARNED.md` — 30 lessons from vista-fm-browser; the
   fm-web takeaway on each lesson is the design input
3. `~/claude/memory/MEMORY.md` and any `project_vehu_docker_dev.md` or
   ancestor-project entries

## Skills to load at session start
- `~/claude/skills/vista-fileman/` — FileMan globals, DD layout, field types
- `~/claude/skills/vista-system/` — VistA package names, namespaces
- `~/claude/skills/ydb-library/` — useful for VEHU dev; fm-web itself does NOT
  talk YDB directly (broker only)

## Two execution environments

### Host (everything for fm-web itself)
- `make install && make test` runs unit tests — no container needed
- `make dev` starts FastAPI on `:8000`
- `make frontend-dev` starts Vite on `:5173`
- Both together: `make dev & make frontend-dev` (Vite proxies `/api` → `:8000`)
- Requires VEHU broker reachable at `localhost:9430` only for integration
  tests and live sign-on

### VEHU container (integration only)
- Used purely as an RPC target — fm-web does not run inside it
- Start via the docker-compose in `~/projects/vehu-docker-dev/`
- Demo creds for dev: `ACCESS=fakedoc1  VERIFY=1Doc!@#$  UCI=VAH`

## Dev workflow
```bash
make install          # uv sync (Python) + npm install (frontend) + pre-commit hooks
make test             # pytest — unit tests only
make test-lf          # rerun last-failed
make watch            # TDD mode — pytest-watch
make cov              # coverage report
make check            # lint + mypy + cov (CI gate)
make format           # ruff format
make frontend-dev     # Vite on :5173
make frontend-build   # static bundle to frontend/dist/
make frontend-lint    # eslint
make dev              # FastAPI (uvicorn) on :8000 with --reload
make push             # check + git push
```

Integration tests (need VEHU broker reachable):
```bash
.venv/bin/pytest tests/ -m integration
```

## Makefile — `.venv/bin/` prefixes required
Never use bare `python`, `pytest`, `ruff`, `mypy`, `uvicorn`, `pre-commit`
in Makefile targets. Always prefix with `.venv/bin/`. See `$(PYTHON)`,
`$(PYTEST)`, `$(RUFF)`, `$(MYPY)`, `$(UVICORN)`, `$(PRECOMMIT)` variables
at the top of `Makefile`. Rationale: parent direnv sets
`VIRTUAL_ENV=/home/rafael/claude/.venv` which hijacks bare tool names.

## Project structure
```
fm-web/
├── docs/
│   ├── ARCHITECTURE.md      # delivery plan; read first
│   └── LESSONS-LEARNED.md   # read second — 30 lessons informing design
├── src/fm_web/              # backend (FastAPI + services + broker adapter)
│   ├── broker/              # XWB NS-mode client + FakeRPCBroker
│   ├── services/            # DataDictionary / Entry / Package / DocLink
│   ├── models/              # Pydantic v2 domain models
│   ├── api/                 # FastAPI routes + deps
│   ├── settings.py          # pydantic-settings
│   └── sites.py             # per-site config loader
├── tests/
│   ├── unit/                # FakeRPCBroker; runs on host in ms
│   ├── contract/            # recorded-fixture contracts for FakeRPCBroker
│   └── integration/         # live VEHU broker; marker @pytest.mark.integration
├── frontend/                # Vite + React 19 + TS
│   ├── src/                 # React app
│   ├── tests/               # Vitest + Testing Library
│   └── package.json
├── docker-compose.yml       # optional dev stack
└── sites.yaml               # per-site VistA config (port, UCI, app context)
```

## Testing conventions
- **TDD first:** write the test, confirm it fails, then implement
- **Three test rings:** unit (ms, host-only) → contract (recorded fixtures)
  → integration (live VEHU broker)
- **No mocks unless unavoidable** — use `FakeRPCBroker` (real fake with same
  interface as `VistARpcBroker`), per the `YdbFake` pattern proven in
  vista-fm-browser
- One test file per source module
- Coverage minimum 80% on `src/fm_web/` excluding `api/` route modules
  (covered via integration/e2e instead)

## Architectural invariants (from lessons learned)
These are not opinions — they are conclusions from real bugs in
vista-fm-browser. See `docs/LESSONS-LEARNED.md`.

1. **FileMan is the API.** Do not re-parse FileMan's on-disk globals. If
   tempted to walk `^DD`, `^DIC`, or any data global, stop and find the RPC
   that does it (`DDR GET DD`, `DDR LISTER`, `DDR GETS ENTRY DATA`).
   (Lessons L1, L3–L11, L30.)
2. **Read-only, enforced at the broker adapter.** Every RPC call passes
   through an allow-list in `fm_web.broker.client`. Adding a new RPC to the
   allow-list requires explicit review — it is the security boundary.
3. **External form by default.** Entry values come back resolved (dates
   rendered, pointers followed, set-of-codes labeled) — done by FileMan
   itself via `FLAGS="E"`. We only touch internal form for debugging.
   (Lessons L18–L20.)
4. **Counts displayed are as-reported-by-FileMan.** No derived totals, no
   quiet deduplication. If FileMan says 2,916, we display 2,916 and mark it
   "via DDR LISTER FILE=N". (Lessons L25–L27.)
5. **The long tail is first-class.** Tiny files are the modal case. Default
   sort is alphabetical, not by entry count. (Lesson L27.)
6. **Suspicious cardinality detector.** Diagnostics page flags any value
   seen across 5+ different files — the B3 tell. (Lesson L16.)

## Adding a dependency
### Python
```bash
# Edit pyproject.toml (dependencies or optional-dependencies.dev)
uv lock && uv sync --extra dev
git add pyproject.toml uv.lock
```
### Frontend
```bash
cd frontend && npm install <pkg>
# commit package.json + package-lock.json
```

## Code style
- Python: ruff only (no black), line 88, rules E/F/I, mypy strict goal
- TypeScript: ESLint default (comes with Vite template), Prettier via
  ESLint rules
- Pre-commit hooks enforce Python style on every commit

## Git conventions
- Main branch: `main`
- Pre-push hook runs `pytest` — push fails if tests fail
- `make push` runs full `check` before pushing
- Commit messages: short imperative ("add DDR LISTER wrapper", "fix session
  expiry")
- Commit `uv.lock` alongside `pyproject.toml` changes
- Commit `frontend/package-lock.json` alongside `frontend/package.json`
  changes

## Claude guidelines
- TDD first — write the test, confirm it fails, then implement
- Prefer editing existing files over creating new ones
- Keep functions small and independently testable
- `logging` not `print()` in library code
- When in doubt about a FileMan API, check `vista-fileman` skill or cite
  the relevant lesson ID from `docs/LESSONS-LEARNED.md`
- If the task mentions reading/parsing a FileMan global directly, STOP —
  architectural invariant #1 says use an RPC. Ask if no RPC seems to fit.
