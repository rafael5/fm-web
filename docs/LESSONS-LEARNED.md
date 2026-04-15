# Lessons Learned — vista-fm-browser → fm-web

**Audience:** the fm-web implementer, reading this before writing a line of
code. Every item here cost time or correctness in vista-fm-browser. Most can
be avoided in fm-web by delegating to FileMan's own RPCs instead of
re-parsing globals.

**Source material:** phase-1 and phase-2 `ASSUMPTIONS-AUDIT.md` and
`phaseN-planning-guide.md` artifacts, `DOWNSTREAM-RULES.md`, the commit log,
and source comments across `src/vista_fm_browser/`.

**Structure:** each lesson has an ID (**L1**…), a one-line finding, the
underlying cause, where it hurt, and **the fm-web takeaway** — which is
often "FileMan handles this; don't re-implement."

---

## Category A — Global-layout gotchas (the expensive ones)

### L1. `_strip_root` must return `(global_name, subscript_prefix)`

**Finding:** The FileMan GL string can be nested — `^DIC(4,`, `^PS(50,`,
`^LEX(757.01,`. The naive "split on `(`, keep the left side" pattern walks
the wrong subtree. In vista-fm-browser this was bug **B3**: 95 files all
reported 2,916 entries (the ^DIC registry size). Total corpus was *20× wrong*
(717k reported, 14.67M actual — the bug was bidirectional).

**Where it hurt:** `file_reader._strip_root` (pre-fix); silently tainted all
phase-2 outputs until the iter-3 audit caught it.

**fm-web takeaway:** Do not walk globals at all for entry access.
`DDR LISTER` and `DDR GETS ENTRY DATA` operate on *file numbers*, not globals.
FileMan already knows where file 4's entries live. If a raw-global view is
ever added (v2+), the parser must be a tuple return with extensive nested-case
fixtures (see `tests/test_file_reader.py::test_*_nested_global`).

### L2. Cross-reference subscripts look like IENs but aren't

**Finding:** `^DPT("B", name, ien)` cross-reference nodes share the top-level
subscript namespace with numeric IENs. Iterators must skip subscripts starting
with `"` (which is how quoted strings appear in YottaDB subscripts) to avoid
counting indexes as entries.

**Where it hurt:** `file_reader.iter_entries` + `count_entries`; one test
(`test_iter_entries_skips_cross_ref_iens`) guards it.

**fm-web takeaway:** `DDR LISTER` only returns real entries — this problem
disappears entirely.

### L3. The 0-node is file header, not an entry — but iterators counted it

**Finding:** `^DPT(0)` holds `"FILE NAME^count^last_ien"`, not a patient.
`count_entries` in vista-fm-browser included it, so every file's count is +1.
Tier classification sometimes hinged on this (an otherwise-empty file
reports 1).

**Where it hurt:** tier boundaries (especially `empty` vs `tiny`).

**fm-web takeaway:** `DDR LISTER` counts entries, not subscripts. The
zero-node is invisible to it.

### L4. Subfile nodes inflate `^DD` top-level subscripts

**Finding:** `^DD` has 8,261 top-level numeric subscripts but only **2,915**
real files. The remainder (5,346) are subfile nodes (decimal file numbers
like 1.001, 1.002) that live alongside top-level files in `^DD`.

**Where it hurt:** phase 1 initially reported 8,261 files; corrected to
2,915 after the audit (rule 6 of DOWNSTREAM-RULES.md). Field-count
denominator similarly wrong: 69,328 (raw) vs 46,790 (top-level only).

**fm-web takeaway:** Enumerate files via file #1 (FILE) through `DDR LISTER`,
not via `^DD` walk. `LIST^DIC` filters to top-level files by construction.

### L5. File #1 (FILE) data lives at top-level `^DIC` subscripts

**Finding:** File #1's "entries" are every other file in the system — they
sit at top-level `^DIC(n)`, not under `^DIC(1, n)`. A generic entry counter
for file #1 returns zero unless special-cased.

**Where it hurt:** `count_entries(1)` was wrong and needed a special case.

**fm-web takeaway:** `DDR LISTER FILE=1` returns the correct list. Again,
let FileMan handle the special case it introduced.

### L6. The INDEX file (#.11) lives at `^DD("IX", …)`, not `^DIC(.11, …)`

**Finding:** Counter-intuitive — a FileMan file whose data global is literally
inside the `^DD` global. `^DIC(.11, 0, "GL")` says `^DD("IX",`.

**Where it hurt:** Initial cross-ref enumeration looked in the wrong place;
surfaced during phase 3 topology.

**fm-web takeaway:** Never hardcode global locations. Ask FileMan via
`$$GET1^DID(file, 0, "GL")` (exposed through `DDR GET DD` or
`XWB GET VARIABLE VALUE`). Fewer magic strings in our codebase.

### L7. MUMPS subscript canonicalization has zero tolerance

**Finding:** `.01` and `0.01` are *different subscripts* in MUMPS. FileMan
stores fields as `.01`; Python naturally produces `0.01` via `str(0.01)`.
Without canonicalization, field lookups silently miss.

**Where it hurt:** `data_dictionary._fmt_field_num` existed specifically to
handle this. Without it, an entire field-level feature appears broken.

**fm-web takeaway:** `DDR GETS ENTRY DATA` accepts FileMan field numbers as
strings (`.01`, `.351`, `9999999`) and does canonicalization internally. We
format once on send; never walk DD globals directly.

---

## Category B — Data-dictionary parsing edge cases

### L8. Type-code grammar is a real grammar

**Finding:** A single FileMan type string packs **prefix flags**, **base
type**, and **modifier suffix** into one unstructured field. Examples seen
in VEHU:

| Raw | Decomposed |
|-----|------------|
| `F` | base=F |
| `RF` | required + base=F |
| `*F` | audit + base=F |
| `R*F` | required + audit + base=F |
| `FX` | base=F + modifier=X |
| `P200` | base=P, pointer_file=200 |
| `P50.68` | base=P, pointer_file=50.68 (**decimal file number!**) |
| `P200'` | required + base=P, pointer_file=200 |
| `DC` | base=DC (**two-letter!**) |
| `NJ3,0` | base=N, numeric_width=3, decimals=0 |
| `MRD` | multiple + required + base=D — **not** multiple + modifier RD |
| `Fa` | base=F + lowercase modifier `a` (semantics unknown) |
| `Ft` | base=F + lowercase modifier `t` |

**Where it hurt:** vista-fm-browser's `type_codes.TypeSpec` grew into a ~200
line state machine with 30+ unit tests, and `MRD` is still an open question
(Q6). Lowercase modifiers `a, t, m, p, w` are preserved but uninterpreted
(Q5). Decimal pointer files were a real bug until fixed.

**fm-web takeaway:** `DDR GET DD` returns the *decoded* type (human-readable
name plus attributes) because FileMan is the authority. We should still
maintain a `TypeSpec` decomposer for our own display enhancements, but it is
no longer on the critical path — if we mis-parse `MRD`, FileMan's label still
renders correctly. That is a huge reduction in risk surface.

### L9. Trailing apostrophe in type strings means "required here"

**Finding:** `P200'` is pointer-to-200 with a required flag, not pointer to
file 200 with a syntax glitch. Stripping trailing `'` before decimal parsing
is mandatory.

**fm-web takeaway:** Same as L8 — `DDR GET DD` decodes this correctly.

### L10. Set-of-codes payload lives in zero-node piece 3, not `^DD("V")`

**Finding:** For S-type fields, `code:label;code:label;...` sits in piece 3 of
`^DD(file, field, 0)`. `^DD(file, field, "V", code)` exists for some sites
but is not universal. Using `"V"` alone gives partial results.

**Where it hurt:** Phase 1.6 set-values were initially empty for half the
S-type fields.

**fm-web takeaway:** `DDR GETS ENTRY DATA FLAGS="E"` returns external
(resolved) set values — no need to parse the encoding.

### L11. Multiple versions of FileMan, one parser

**Finding:** Even within VEHU there are signs of mixed FileMan-22.0 and
22.2 DD conventions (INDEX file location, new-style cross-refs, extended
field attributes). A single global-walker has to handle both.

**fm-web takeaway:** FileMan's own routines handle their own version drift.
Sites running older FileMan still get correct answers from `DDR GET DD`.

---

## Category C — Package attribution ambiguity

### L12. PACKAGE file (`^DIC(9.4)`) is incomplete in practice

**Finding:** In VEHU, 139 files (4.8%) and ~61k entries (8.5% of total)
cannot be attributed to any package by `^DIC(9.4)` PREFIX lookup. High-volume
PCE/IHS files (OUTPATIENT ENCOUNTER, VISIT, V CPT) fall into this gap — the
PACKAGE entries exist without PREFIX fields populated.

**Where it hurt:** Required a three-heuristic attribution layer (direct,
prefix-scan, empirical/canonical range) plus an explicit `(unattributed)`
bucket preserved through every downstream output. Rule 3 of
DOWNSTREAM-RULES.md encodes this permanently.

**fm-web takeaway:** We can use `DDR LISTER` on file 9.4 to show PACKAGE
contents verbatim — no heuristics needed for the browser. fm-web does not
need to "fix" attribution; it needs to honestly reflect what FileMan knows.
Any analysis pipeline built on top of fm-web will need the same heuristic
layer we built, but that's a consumer problem.

### L13. Package count has an off-by-one

**Finding:** `^DIC(9.4)` iteration yields 469 numeric IENs; inventory
reported 470 total (Q8 from phase-1 audit). Likely header metadata included
by one walker and not the other. Unresolved, low priority.

**fm-web takeaway:** Count what FileMan counts — whatever `DDR LISTER FILE=9.4
FLAGS="P"` returns is the answer, by definition.

### L14. Confidence must survive the pipeline

**Finding:** Three heuristics produce five provenance values (`direct`,
`prefix`, `range_canonical`, `range_empirical`, `unattributed`) and three
confidence levels (`high`, `med`, `low`). Consumers that silently merge them
destroy traceability.

**fm-web takeaway:** Not applicable to v1 (no attribution). If/when
attribution is added, pass confidence through every API response. Document in
the OpenAPI schema.

---

## Category D — Count / volume pitfalls

### L15. Empty files concentrate in VA FILEMAN

**Finding:** 106 files are empty in VEHU post-B3 fix; 33 of those belong to
VA FILEMAN (configuration/template files that legitimately ship empty).
Filtering "empty" out of analysis hides a real data-distribution signal.

**fm-web takeaway:** Show empty files with a clear `0` count; don't hide
them. If entry browser is asked for an empty file, show an empty-state panel,
not an error.

### L16. Reality check: "95 files all report exactly N" is always a bug

**Finding:** This was the iter-3 audit's tell for B3. When a summary shows a
suspiciously round-numbered mode (2,916 × 95), investigate global-root
parsing before anything else.

**fm-web takeaway:** Build a "suspicious cardinality detector" into the
diagnostics page — any file-count collision seen more than ~5 times across
different files should flash a warning.

### L17. VEHU is not stable — re-runs see drift

**Finding:** Between iter-1 and iter-2 runs, total entries drifted 10 entries
(717,892 → 717,902). Low-latency demo data mutates. Do not rely on exact
equality across runs; allow small deltas.

**fm-web takeaway:** Counts in fm-web are always "as of now." Cache with TTL
(minutes, not hours). Show `fetched_at` timestamps in the UI so users can
tell stale data.

---

## Category E — Date / time handling

### L18. FileMan dates are offset from year 1700

**Finding:** `YYYMMDD.HHMMSS` where `YYY = year - 1700`. Date
`3160101.1400` → 2016-01-01 14:00:00. Not a standard epoch anywhere else.

**fm-web takeaway:** `DDR GETS ENTRY DATA FLAGS="E"` returns external format
(`"JAN 01, 2016@14:00"`) — we don't parse the internal form in v1. If we add
an internal-form view (for debugging), port the proven `fm_datetime` module.

### L19. Time-fraction trailing zeros are dropped

**Finding:** `14:30:00` stores as fractional `0.143`, **not** `0.1430`.
Parsers must right-pad to 6 digits before reading HHMMSS. Easy to get wrong.

**fm-web takeaway:** Same as L18 — FileMan's external form avoids this.

### L20. Partial dates use `0` for unknown month/day

**Finding:** `3160000` → "sometime in 2016." `datetime.date` rejects
month/day=0, so must normalize to 1 with a precision flag, or use a custom
date type.

**fm-web takeaway:** External form handles partial dates ("2016", "JAN
2016"). If internal form is ever needed, preserve the precision level —
don't silently upgrade "2016" to "Jan 1, 2016."

---

## Category F — Environment / toolchain

### L21. `ydb_gbldir` must point to the right database

**Finding:** vista-fm-browser's big footgun: `source /usr/local/etc/ydb_env_set`
alone points at an **empty** database. Must also source
`/home/vehu/etc/env` and export `ydb_gbldir=/home/vehu/g/vehu.gld` — or
simpler, `source /etc/bashrc` which wraps all three.

**fm-web takeaway:** This disappears entirely because fm-web never speaks
YottaDB directly. Broker-only.

### L22. Python venv created as root inside container is unusable on host

**Finding:** `docker compose exec vehu ... uv pip install` creates `.venv/`
owned by root. The direnv on host then fails silently on permission errors.
This was encountered **during the B3 fix** and blocked host `make test`.

**fm-web takeaway:** Use a **separate venv per context**. Host:
`fm-web/.venv`. Container: `/opt/venv` (outside the mounted project tree, so
mount ownership isn't conflated). Document the convention in README.

### L23. OUTPUT_DIR convention shifted mid-project

**Finding:** Early scripts wrote to `~/data/vista-fm-browser/phaseN/`. Mid-
project moved to `<repo>/output/phaseN/` via
`Path(__file__).resolve().parents[2] / "output" / "phaseN"`. phase2-viz.py
still had the old path until caught in iter 4.

**fm-web takeaway:** fm-web doesn't produce analysis outputs — not
applicable. But: lock path conventions in settings.py at day one.

### L24. Host vs container split is a permanent seam

**Finding:** YottaDB Python bindings do not exist on host. Anything touching
the live DB must run in-container. This forced unit tests (host, YdbFake) and
integration tests (container, real YDB) to split — and a pre-commit hook
that runs `pytest` on the host would fail the integration-mark tests.

**fm-web takeaway:** Broker-only = no split. Unit + integration can run on
the same machine that can reach the broker port. CI runs integration in a
job that starts VEHU via docker-compose service.

---

## Category G — Downstream rules (the contracts)

These became `DOWNSTREAM-RULES.md` in vista-fm-browser; they're worth
re-stating for fm-web:

### L25. Denominators must be locked

**Finding:** Mixed denominators (8,261 vs 2,915 files; 69,328 vs 46,790
fields) caused repeated re-runs.

**fm-web takeaway:** The UI displays *counts as reported by FileMan* with
clear labels. No derived totals.

### L26. Provenance / confidence must be carried end-to-end

**fm-web takeaway:** Every service response that aggregates (packages,
cross-refs) must include the underlying source (`via="file 9.4 walk"`,
`via="^DIC(9.4) PACKAGE"`, etc.) in an explicit field.

### L27. The long tail is the corpus

**Finding:** 2,298 files have 1–99 entries; 16 files carry the massive tier.
The median file is tiny. Charts that truncate the long tail hide 78% of
files.

**fm-web takeaway:** The entry browser must handle tiny files as first-class
citizens, not edge cases. The file browser's default sort is alphabetical,
not by entry count, to surface the tail.

---

## Category H — Process lessons (non-technical)

### L28. Audit every iteration

**Finding:** B3 was not caught by tests — it was caught by the iter-3
`ASSUMPTIONS-AUDIT.md` pass. Tests verified the code did what the coder
thought; the audit verified the result matched reality.

**fm-web takeaway:** Keep the pattern. Each milestone gets its own audit
document listing every claim made by its outputs and classifying each as
VERIFIED / UNVERIFIED / LIMITATION / BUG.

### L29. Planning guide > commit message

**Finding:** `phaseN-planning-guide.md` was the living memory between
sessions; commit messages couldn't carry it.

**fm-web takeaway:** Keep a `docs/ENGINEERING-LOG.md` updated per sprint with
findings and forward tasks. Makes multi-session context free.

### L30. Delegate to the authoritative implementation

**Finding:** The single biggest accelerant in the vista-fm-browser → fm-web
transition is giving up on our own FileMan parser. Every line of L8-L11 is
a bug we don't inherit.

**fm-web takeaway:** "FileMan is the API" is the core mental model. If we
find ourselves parsing FileMan storage formats, back up and look for the
RPC that already does it.

---

## Open questions carried forward

| ID | Question | Relevance to fm-web |
|----|----------|---------------------|
| Q5 | Semantics of lowercase type modifiers (`a`, `t`, `m`, `p`, `w`) | Low — `DDR GET DD` gives us decoded attributes |
| Q6 | `MRD` compound mis-parse in our decomposer | Low — we won't decompose on the hot path |
| Q7 | Are the 139 unattributed files truly absent from `^DIC(9.4)` or walk artifacts? | Medium — worth verifying once via `DDR LISTER FILE=9.4` against a site and cross-checking |
| Q8 | Package count 470 vs 469 | Very low — report what FileMan reports |

---

## Summary — what fm-web inherits and what it sheds

**Inherits (valuable):**
- The XWB NS-mode broker wire implementation (`rpc_broker.py`) — proven
  against VEHU, with demo credentials in comments. Direct port.
- Domain vocabulary: file / field / package / cross-reference / type-code /
  provenance — Pydantic v2 models re-typed clean.
- VEHU container setup and `/etc/bashrc` dance (only relevant for
  integration tests that spin up VEHU).
- The TDD rhythm and `YdbFake` pattern, ported as `FakeRPCBroker`.

**Sheds (liability):**
- The `^DD` / `^DIC` walker (`data_dictionary.py`) — replaced by `DDR GET DD`.
- The `^global(subtree)` walker (`file_reader.py`) — replaced by `DDR LISTER`
  and `DDR GETS ENTRY DATA`.
- The three-heuristic package attribution layer — unnecessary for a browser.
- The FileMan-date internal-form decoder (`fm_datetime.py`) — external form
  via `DDR GETS FLAGS="E"` is the default.
- The `_strip_root` global-root parser — not needed when we don't walk
  globals.
- OUTPUT_DIR conventions — fm-web has no analysis outputs.

Every bullet above is a surface area we stop maintaining. That is the payoff
of the clean break.
