# Phase 7: Public-Repo Audit - Pattern Map

**Mapped:** 2026-05-23
**Files analyzed:** 6 (3 new, 3 modified)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/verify_public_repo.py` (NEW) | script | input: `.secrets-denylist` + worktree + git history; output: stderr summary + exit code | `scripts/check_public_discipline.py` | exact (same role, same data flow, same pattern source) |
| `tests/unit/test_check_public_discipline.py` (NEW) | test | input: tmp denylist + fake fixture; output: pytest assertions on `main()` return code | `tests/unit/test_score_math.py` (parametrized pure-function shape) plus `tests/unit/test_calibration_runner.py` (monkeypatch-module-constant pattern) | role-match (parametrize style) plus pattern-match (DENYLIST patching) |
| `.planning/phases/07-public-repo-audit/07-FINDINGS.md` (NEW) | artifact | input: human-authored verdict, grep summary counts, links; output: phase verdict markdown | `.planning/phases/audit/findings.md` (Phase 1 findings.md) | exact (same phase-verdict role, same evidence-linking style) |
| `Makefile` (MODIFIED, add `verify-public-repo` target) | config | input: shell invocation; output: one-line `uv run` wrapper | Existing `Makefile` targets (`setup-sheet`, `eval-report`) | exact (one-line `uv run python ...` wrapper) |
| `README.md` (MODIFIED, add "Local setup" denylist step) | docs | input: numbered-list prose; output: published markdown | Existing README "Run it" numbered list (lines 82-98) | exact (numbered code-block setup steps) |
| `.planning/REQUIREMENTS.md` (MODIFIED, flip REPO-01/03/04 to Complete) | artifact | input: row-status edit; output: traceability table update | Existing rows in traceability table (lines 100-128) where Complete status is already established for EVAL-*, NARR-*, HARD-*, POLISH-* | exact (same table, same cell semantics) |

## Pattern Assignments

### `scripts/verify_public_repo.py` (NEW, script, verify-and-report)

**Analog:** `scripts/check_public_discipline.py` (67 lines, fully annotated, strict-mypy clean)

**Module docstring + imports pattern** (`scripts/check_public_discipline.py:1-18`):
```python
"""Pre-commit guard: block staged content that violates public-repo discipline.

Patterns live in a local-only file (.secrets-denylist, gitignored) so the
sensitive terms themselves never enter the public repository. If that file is
absent (e.g. a fresh clone by another contributor) the check passes silently
rather than breaking unrelated commits.

Usage: invoked by pre-commit with the list of staged files as argv.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

DENYLIST = Path(__file__).resolve().parent.parent / ".secrets-denylist"
```

Notes for the new script: replicate the docstring shape (purpose, denylist-file framing, usage line) but for the verify use case. The `DENYLIST` constant resolution (`Path(__file__).resolve().parent.parent / ".secrets-denylist"`) is the exact pattern to reuse, because it makes the verify script and pre-commit guard read from the same file regardless of cwd. Per D-Claude's-Discretion, the planner may either duplicate `_load_patterns()` (5 lines, DRY cost low) or extract to `scripts/_denylist.py` and import; CONTEXT.md `<deferred>` says "Not Phase 7's call" if duplication feels real.

**Pattern-loading pattern to reuse verbatim or import** (`scripts/check_public_discipline.py:21-30`):
```python
def _load_patterns() -> list[re.Pattern[str]]:
    if not DENYLIST.exists():
        return []
    patterns: list[re.Pattern[str]] = []
    for raw in DENYLIST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(re.compile(line, re.IGNORECASE))
    return patterns
```

Notes: case-insensitive regex per line, blank and `#`-comment lines skipped, returns `[]` on missing file. The verify script's behavior diverges here per D-08 (`scripts/verify_public_repo.py` exits non-zero with a clear stderr message instead of silently returning empty patterns), so the script will need a small wrapper that calls `_load_patterns()` (or its equivalent) and then explicitly checks `DENYLIST.exists()` before proceeding.

**Subprocess + main pattern** (`scripts/check_public_discipline.py:33-66`):
```python
def _staged_content(path: str) -> str:
    result = subprocess.run(
        ["git", "show", f":{path}"],
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else ""


def main(argv: list[str]) -> int:
    patterns = _load_patterns()
    if not patterns:
        return 0

    violations: list[str] = []
    for path in argv:
        content = _staged_content(path)
        for pat in patterns:
            if pat.search(content) or pat.search(path):
                violations.append(f"  {path}: matches /{pat.pattern}/i")

    if violations:
        sys.stderr.write(
            "public-repo-discipline check failed; staged changes contain "
            "denylisted terms:\n" + "\n".join(violations) + "\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

Notes for the new script:
- `subprocess.run(..., capture_output=True, text=True)` is the project's pattern for shelling out to git. The verify script extends this to two passes: (a) `rg --files-with-matches <pattern>` over the worktree (or a `git ls-files` + `re.search` loop if `rg` is not a tool dependency the project carries; planner discretion), (b) `git log --all -p` piped through grep. The CONTEXT.md `<decisions>` D-01 says ripgrep is acceptable; verify the tool is on the operator's PATH and add a clear error if missing.
- The `main(argv: list[str]) -> int` signature plus `if __name__ == "__main__": raise SystemExit(main(sys.argv[1:]))` is the canonical entry-point shape. The verify script should follow the same shape so the test pattern (call `main([])` directly) carries over if a unit test is ever added.
- Public-repo safety: per D-11 the verify script MUST NOT print raw match text to stdout. The existing pre-commit script DOES print path + pattern to stderr at line 57-60; the verify script must NOT do this. Instead, summary counts only ("0 hits in tracked content, 0 hits in history") plus a non-zero exit code that prompts the operator to re-run locally with a per-hit listing if needed (planner discretion on how to expose the local-only detail surface; one option: a `--verbose` flag that writes to a gitignored path).
- Exit codes per D-Claude's-Discretion: 0 = clean, 1 = hit found, 2 = denylist missing. Mirror the `return 0` / `return 1` shape; add `return 2` for the missing-denylist branch with an explicit "verification needs the local denylist; create it (see README) before running" stderr message (D-08).
- Per D-17, the script knows nothing about `../poc_scraper-FULL-BACKUP.bundle`. The bundle is outside the repo root; the script's scan boundary is the current working tree + its git history only.

**Path filtering pattern** (the `.secrets-denylist` itself is the one allowed location for the pattern, per D-03):
```python
# Filter the denylist file itself out of pass (a) results before counting.
# `.secrets-denylist` is gitignored, but a worktree scan still sees it.
# pass (b) (git log) will never match the file because it is gitignored.
```
This is a new branch (no analog in `check_public_discipline.py`); the planner adds an explicit `if path == ".secrets-denylist": continue` (or equivalent) in the worktree pass.

---

### `tests/unit/test_check_public_discipline.py` (NEW, test, parametrized pure-function)

**Analog 1 (parametrize style):** `tests/unit/test_score_math.py`
**Analog 2 (monkeypatch-module-constant style):** `tests/unit/test_calibration_runner.py`
**Analog 3 (parametrize with case-table):** `tests/unit/test_retry.py:127-140`

**Imports + helper-builder pattern** (`tests/unit/test_score_math.py:1-20`):
```python
from __future__ import annotations

import pytest

from src.icp_config import get_config
from src.models import RubricBreakdown
from src.score import compute_total


def _rb(sv: float, ai: float, stage: float, ch: float) -> RubricBreakdown:
    return RubricBreakdown(
        support_volume=sv,
        ai_maturity=ai,
        stage_fit=stage,
        channel_breadth=ch,
        support_volume_reason="r",
        ai_maturity_reason="r",
        stage_fit_reason="r",
        channel_breadth_reason="r",
    )
```

Notes: `from __future__ import annotations`, top-level `import pytest`, direct module import (`from scripts.check_public_discipline import main`), small helper function at the top to build common fixtures (here, the equivalent would be a `_write_fixture(tmp_path, body)` or `_make_argv(...)` helper).

**Module-constant patching pattern** (`tests/unit/test_calibration_runner.py:307`):
```python
monkeypatch.setattr(mod, "get_settings", lambda: no_keys)
```

Notes: the project patches module-level constants via `monkeypatch.setattr(module, "CONSTANT_NAME", new_value)`. For the new test:
```python
import scripts.check_public_discipline as mod

def test_main_returns_one_on_content_match(tmp_path, monkeypatch):
    fake_denylist = tmp_path / ".secrets-denylist"
    fake_denylist.write_text("fake-denylisted-term-for-test\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DENYLIST", fake_denylist)
    # ... stage a fixture file, call mod.main([str(fixture_path)]), assert == 1
```

Critical: per CONTEXT.md `<specifics>` and D-05, the fake term MUST be a publishable placeholder (the example `"fake-denylisted-term-for-test"` is fine). The hiring company name MUST NOT appear in the test file.

**Parametrize-with-case-table pattern** (`tests/unit/test_retry.py:127-140`):
```python
@pytest.mark.parametrize("retry_after_value, expected", [("30", 30.0), ("0", 0.0)])
def test_wait_returns_exact_retry_after_with_no_cap(
    retry_after_value: str, expected: float
) -> None:
    # D-05: no max, no min, no cap composition. Honor the header exactly.
    fallback = wait_exponential(multiplier=1, min=1, max=15)
    wait = retry_after_aware_wait(fallback=fallback)
    # ...
```

Notes: `@pytest.mark.parametrize` with a comma-joined string of names and a list of tuples. Each tuple is one case. Type annotations on every parameter (strict mypy applies, though `tests/` is exempt from `ARG` per `pyproject.toml:53-54`; CI scopes mypy to `src evals` only per the calibration test header comment at lines 1-9).

For Phase 7, per D-06 the two parametrized cases are:
```python
@pytest.mark.parametrize(
    "case_id, body, path_suffix, expected",
    [
        ("content-match", "this file mentions fake-denylisted-term-for-test\n", "ok.txt", 1),
        ("path-match", "harmless body\n", "fake-denylisted-term-for-test.txt", 1),
    ],
)
def test_main_flags_violations(...)
```

**Tmp-file + monkeypatch fixture pattern** (composite, drawing from `tests/unit/test_calibration_runner.py` patterns):
```python
def test_X(tmp_path, monkeypatch):
    fake_denylist = tmp_path / ".secrets-denylist"
    fake_denylist.write_text("fake-denylisted-term-for-test\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DENYLIST", fake_denylist)

    fixture = tmp_path / path_suffix
    fixture.write_text(body, encoding="utf-8")

    # NOTE: main() calls subprocess `git show :path` for staged content.
    # In a unit test, the file is not staged, so _staged_content() returns "".
    # That means the content-match case must also patch _staged_content OR
    # use monkeypatch on subprocess.run to inject the body. Planner choice:
    # easier and lower-risk to patch _staged_content directly:
    monkeypatch.setattr(mod, "_staged_content", lambda p: body if p == str(fixture) else "")

    assert mod.main([str(fixture)]) == 1
```

This is a critical pattern detail the planner must surface: `main()` invokes `_staged_content()`, which shells out to `git show :<path>`. In a unit test, the file is not staged, so the real `_staged_content` returns `""` and the content-match case fails by accident. The two safe options are (a) `monkeypatch.setattr(mod, "_staged_content", lambda p: body)`, or (b) refactor `main()` to take a content-provider callable (over-engineering for two test cases). Option (a) is the obvious choice.

---

### `.planning/phases/07-public-repo-audit/07-FINDINGS.md` (NEW, artifact, phase-verdict markdown)

**Analog:** `.planning/phases/audit/findings.md` (Phase 1 findings.md, 378 lines, the binding precedent per CONTEXT.md D-10)

**Header pattern** (`.planning/phases/audit/findings.md:1-6`):
```markdown
# Groundedness Audit Findings

**Audit date:** 2026-05-15
**Auditor:** Claude
**Phase context:** Phase 1 of 8 (Groundedness Audit)
**Requirement:** AUDIT-01 (gap enumeration), AUDIT-02 (claim-pairing sample), AUDIT-03 (open-question decisions)
```

For Phase 7 the equivalent header is:
```markdown
# Phase 7 Public-Repo Audit Findings

**Audit date:** 2026-05-23
**Auditor:** Claude
**Phase context:** Phase 7 of 8 (Public-Repo Audit)
**Requirements:** REPO-01 (no hiring company name in content, paths, or reachable history), REPO-03 (deny-list grep with rewrite-vs-document decision), REPO-04 (pre-commit hook blocks the name)
```

**Section-header + numbered-section pattern** (`.planning/phases/audit/findings.md:8, 22, 31`):
```markdown
## 1. Groundedness Contract (D-03)
## 2. Three Groundedness Seams (architectural context)
## 3. Gap Enumeration (AUDIT-01 deliverable)
```

Numbered top-level sections (`## 1.`, `## 2.`, `## 3.`) with a parenthesized scope label tying the section to a requirement or design decision. Phase 7 sections (per CONTEXT.md D-10/D-11/D-12/D-14/D-15/D-16) will follow this shape; suggested ordering, planner discretion:

```markdown
## 1. Per-Requirement Verdict Table (D-12)
## 2. Grep-Pass Summary (D-11)
## 3. Pre-Commit Guard Confirmation (REPO-04)
## 4. Forensic Bundle Retention Policy (D-14, D-15)
## 5. Re-Scrub Procedure Pointer (D-16)
## 6. Timeline Pointer to PROJECT.md (2026-05-14 rows)
```

**Per-requirement-row pattern** (`.planning/phases/audit/findings.md:35-89` enumerates GAP-01 through GAP-08 each with a Location / Contract violation / Current behavior / Failure shape sub-structure). For Phase 7 the equivalent is a per-requirement-verdict table at the TOP (D-12 locks the table-at-the-top requirement). Table shape, three rows:

```markdown
| Requirement | Verdict | Evidence |
|-------------|---------|----------|
| REPO-01 | Complete | `make verify-public-repo` run on 2026-05-23 at commit <SHA>: 0 hits in tracked content, 0 hits in history reachable from any ref. Source: `scripts/verify_public_repo.py`. |
| REPO-03 | Complete | History rewritten via `git filter-repo` on 2026-05-14, force-pushed; pre-rewrite preserved offline at `../poc_scraper-FULL-BACKUP.bundle`. Decision recorded at `.planning/PROJECT.md` Key Decisions row "History rewritten and force-pushed to purge the hiring company name (2026-05-14)". Rationale at `.planning/phases/audit/findings.md:288-294` (OQ2). |
| REPO-04 | Complete | Pre-commit hook at `.pre-commit-config.yaml:21-27` invokes `scripts/check_public_discipline.py`. Unit test at `tests/unit/test_check_public_discipline.py` covers content-match and path-match branches. |
```

**Evidence-linking style** (`.planning/phases/audit/findings.md` throughout): every claim links to a `file:line` reference or a code path. Phase 7 follows the same convention; no claim without a citation.

**Closing-section pattern** (`.planning/phases/audit/findings.md:370-378`):
```markdown
## Audit Sign-off

Date: 2026-05-15

All four ROADMAP Phase 1 success criteria are satisfied by this document:
1. findings.md exists with file:line refs for all eight gaps GAP-01 through GAP-08 (AUDIT-01)
2. 12 hooks hand-paired claim-to-evidence with grounded/partial/fabricated verdicts and a claim-pairing summary (AUDIT-02)
3. All six open questions OQ1 through OQ6 have documented binding decisions (AUDIT-03)
4. The Phase 2 code-change handoff lists CHANGE-01 through CHANGE-06 naming target files, change shapes, and FIX requirements (ROADMAP SC4)
```

Phase 7 closing section maps Phase 7 success criteria (4 items from `.planning/ROADMAP.md` lines 204-209) to the evidence in FINDINGS.md, mirroring this shape.

**Constraint reminders applied to FINDINGS.md:**
- Per CONTEXT.md `<code_context>` "Established Patterns": no emojis. The Phase 1 analog has no emojis; preserve.
- FINDINGS.md is internal (Phase 8 README does not link it per D-13) but the project has not formalized a separate "no em-dashes in internal markdown" rule; the Phase 1 analog uses em-dashes freely (`.planning/phases/audit/findings.md:14`: "This is the 'moderate' contract."). Planner discretion. Per CLAUDE.md, em-dashes are forbidden only in **published** markdown; FINDINGS.md is internal, so em-dashes are permissible if needed for clarity. Recommendation: stay em-dash-free for consistency with the README change being landed in the same phase.
- Per D-11, FINDINGS.md records summary counts only, never raw match text. The hiring company name MUST NOT appear in this file under any circumstance.

---

### `Makefile` (MODIFIED, config, one-line `uv run` wrapper)

**Analog:** Existing `Makefile` targets (`setup-sheet:` line 7-8, `eval-report:` line 27-28, `run-demo:` line 13-14)

**One-line `uv run` wrapper pattern** (`Makefile:7-8`):
```makefile
setup-sheet:
	uv run python -m scripts.setup_sheet
```

```makefile
eval-report:
	uv run python -m evals.report
```

```makefile
run-demo:
	DEMO_BUNDLE=fixtures/demo-bundle uv run python -m src.pipeline
```

Notes:
- Targets are kebab-case (`setup-sheet`, `eval-report`, `verify-public-repo`).
- Body is a single `uv run python ...` line, tab-indented (Makefile syntax).
- Scripts that live at `scripts/*.py` are invoked via `python -m scripts.<name>` (module form), not `python scripts/<name>.py` (path form). The existing `setup-sheet` target proves this. For Phase 7, the target shape is:
  ```makefile
  verify-public-repo:
  	uv run python -m scripts.verify_public_repo
  ```
- The `.PHONY` declaration at `Makefile:1` must be extended with `verify-public-repo`:
  ```makefile
  .PHONY: install setup-sheet run run-demo eval eval-live eval-fixtures eval-calibration eval-report test smoke lint format typecheck clean verify-public-repo
  ```

Per CONTEXT.md `<deferred>`: adding `make verify-public-repo` to CI as a required check is deferred to planner discretion (the issue is shallow clones; `git log --all -p` cannot run on a shallow checkout). Default: do NOT add it to CI; the unit test for `check_public_discipline.py` runs in CI regardless and exercises the guard surface that matters for contributor commits.

---

### `README.md` (MODIFIED, docs, numbered setup steps in published markdown)

**Analog:** Existing README "Run it" numbered list (`README.md:82-98`)

**Numbered-step + code-fence pattern** (`README.md:82-98`):
```markdown
## Run it

\`\`\`bash
# 1. Install
make install

# 2. Add API keys to .env (copy from .env.example)
cp .env.example .env
# fill in DEEPSEEK_API_KEY (recommended) OR NVIDIA_API_KEY (free fallback),
# plus EXA_API_KEY, BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID.
# point GOOGLE_APPLICATION_CREDENTIALS at a Sheets-enabled service-account JSON

# 3. Drop domains into inputs/accounts.csv (one per line, header `domain`)

# 4. Ship
make run
\`\`\`
```

Notes:
- Numbered steps live inside a single bash code fence with `# N. <step>` comment headers.
- Comments above each step expand on the rationale or list which env vars to set.
- Conversational prose paragraphs appear AFTER the code block (lines 100-106 in the existing README) rather than between steps.

For Phase 7 per D-09: a short numbered step describing `.secrets-denylist` recreation, with the constraints that (a) the file is gitignored, (b) one regex per line, (c) used by both the pre-commit guard and the verify script, (d) the sensitive term itself is NEVER shown in the README (the term lives only in the local denylist on the operator's machine).

Recommended placement: a new H3 "Local setup" subsection nested under "## Run it" (line 82) so the denylist recreation appears as a setup-time step the operator does once. Suggested skeleton (planner authors final wording per D-Claude's-Discretion):

```markdown
### Local setup

If you want the public-repo guard active locally (recommended for any contributor pushing to the public repo), create `.secrets-denylist` at the repo root. The file is gitignored by design so the sensitive terms never enter version control. Add one regex per line; the file is read by both the pre-commit hook (`scripts/check_public_discipline.py`) and the verification script (`make verify-public-repo`).
```

**Critical constraint per CLAUDE.md and CONTEXT.md `<code_context>`:** README.md is published markdown. No em-dashes. Use commas, parentheses, or rewrite. The existing README at line 14 contains a SINGLE em-dash (`Rubric, Inputs, and Results tabs from a real run.` no, that's an em-dash mid-sentence on line 14: "real run."). Quick grep on README needed before commit; new copy in Phase 7 MUST be em-dash-free.

---

### `.planning/REQUIREMENTS.md` (MODIFIED, artifact, traceability-table cell flips)

**Analog:** Existing rows in the traceability table at `.planning/REQUIREMENTS.md:100-128` where Complete status is already established for EVAL-*, NARR-*, HARD-*, POLISH-*

**Table-row Complete pattern** (`.planning/REQUIREMENTS.md:110-124`):
```markdown
| EVAL-01 | Phase 3 | Complete |
| EVAL-02 | Phase 3 | Complete |
| EVAL-03 | Phase 3 | Complete |
| EVAL-04 | Phase 3 | Complete |
| NARR-01 | Phase 4 | Complete |
| NARR-02 | Phase 4 | Complete |
| NARR-03 | Phase 4 | Complete |
| HARD-01 | Phase 5 | Complete |
| HARD-02 | Phase 5 | Complete |
| HARD-03 | Phase 5 | Complete |
| HARD-04 | Phase 5 | Complete |
| POLISH-01 | Phase 6 | Complete |
| POLISH-02 | Phase 6 | Complete |
| POLISH-03 | Phase 6 | Complete |
| POLISH-04 | Phase 6 | Complete |
```

Current rows to flip (`.planning/REQUIREMENTS.md:125-128`):
```markdown
| REPO-01 | Phase 7 | Pending |
| REPO-02 | Phase 7 | Withdrawn (scope narrowed 2026-05-14) |
| REPO-03 | Phase 7 | Pending |
| REPO-04 | Phase 7 | Pending |
```

Target state (per D-12, in the SAME commit as FINDINGS.md):
```markdown
| REPO-01 | Phase 7 | Complete |
| REPO-02 | Phase 7 | Withdrawn (scope narrowed 2026-05-14) |
| REPO-03 | Phase 7 | Complete |
| REPO-04 | Phase 7 | Complete |
```

Notes:
- REPO-02 row is unchanged. It stays "Withdrawn (scope narrowed 2026-05-14)". Do NOT touch.
- Per D-12 atomicity: the flip lands in the SAME commit as `07-FINDINGS.md`. The commit message must reference REPO-01/03/04 closure. Conventional-commit shape per CLAUDE.md.
- Also flip the checkbox state at lines 54-56 from `- [ ]` to `- [x]`:
  ```markdown
  - [ ] **REPO-01**: ...
  - [ ] **REPO-03**: ...
  - [ ] **REPO-04**: ...
  ```
  becomes
  ```markdown
  - [x] **REPO-01**: ...
  - [x] **REPO-03**: ...
  - [x] **REPO-04**: ...
  ```
  This matches the pattern at lines 27-30 (EVAL-*) and 33-36 (NARR-*) where Complete is reflected in both the checklist AND the traceability table.

---

## Shared Patterns

### Strict-mypy Annotation Style
**Source:** `scripts/check_public_discipline.py` (every function fully annotated; `_load_patterns() -> list[re.Pattern[str]]`, `_staged_content(path: str) -> str`, `main(argv: list[str]) -> int`)
**Apply to:** `scripts/verify_public_repo.py` (and the test file's helper functions)

Per CLAUDE.md and `pyproject.toml:56-66`, mypy is strict with `disallow_untyped_defs`. Every function, including private helpers, MUST be fully annotated. CI runs mypy on `src evals` only (per `Makefile:44-45` and the `# mypy: disable-error-code=arg-type` header at `tests/unit/test_calibration_runner.py:1-9`), so `scripts/` and `tests/` are not strict-mypy-gated at CI time, but the project convention is to annotate them anyway. The existing `scripts/check_public_discipline.py` does this; follow the same shape.

### `from __future__ import annotations`
**Source:** `scripts/check_public_discipline.py:11`, `tests/unit/test_score_math.py:1`, `tests/unit/test_retry.py:1`, every file in `src/`
**Apply to:** Both new Python files (`scripts/verify_public_repo.py`, `tests/unit/test_check_public_discipline.py`)

Every Python file in the project starts with `from __future__ import annotations`. New files MUST too.

### Module-Constant Pattern + Path-from-`__file__`
**Source:** `scripts/check_public_discipline.py:18` (`DENYLIST = Path(__file__).resolve().parent.parent / ".secrets-denylist"`); `scripts/setup_sheet.py:28` (`ENV_PATH = Path(__file__).resolve().parent.parent / ".env"`)
**Apply to:** `scripts/verify_public_repo.py` (resolve `.secrets-denylist` relative to the script file, not cwd)

The pattern `Path(__file__).resolve().parent.parent / "<sibling-file>"` makes the script cwd-independent. Use this verbatim in the new verify script so the test pattern (`monkeypatch.setattr(mod, "DENYLIST", tmp_path / ".secrets-denylist")`) works the same way it does for the pre-commit guard.

### Conventional Commits (No Emojis)
**Source:** Recent git log (per gitStatus: `feat(06-04): ...`, `test(06-04): ...`, `docs(06-04): ...`)
**Apply to:** The Phase 7 commit (FINDINGS.md + REQUIREMENTS.md flips, plus possibly co-located script + Makefile changes)

Recommended commit message shape (planner authors final wording):
```
docs(07): close REPO-01/03/04 with audit findings and verify-script

Adds scripts/verify_public_repo.py + make verify-public-repo + unit test
for the existing pre-commit guard. Flips REPO-01, REPO-03, REPO-04 from
Pending to Complete in REQUIREMENTS.md traceability table. FINDINGS.md
records grep-pass counts (no raw matches) and the bundle retention policy.
```

Per CLAUDE.md: no emojis, no em-dashes in published markdown (README), conventional commit style. The git log shows scope tags like `(06-04)`; for Phase 7 the scope tag is `(07)`.

### Subprocess for Git Operations
**Source:** `scripts/check_public_discipline.py:33-41`
**Apply to:** `scripts/verify_public_repo.py` (two passes: ripgrep over worktree + `git log --all -p | grep` over history)

`subprocess.run(..., capture_output=True, text=True)` is the canonical project pattern for shelling out. The new script extends this to two `subprocess.run` invocations; check `returncode` for each and surface a clear error on non-zero.

### Public-Repo Discipline (Pre-Commit Guard Active)
**Source:** `.pre-commit-config.yaml:21-27` (the `local` repo hook wires `scripts/check_public_discipline.py`)
**Apply to:** All Phase 7 artifacts (the hiring company name must NEVER appear in any commit)

The pre-commit hook will block any commit that introduces the hiring name in staged content or paths. Per CONTEXT.md `<specifics>`: "The hiring company name must never appear in any committed Phase 7 artifact, including grep transcripts. The denylist file stores the term; FINDINGS.md, the verify script's source code, and the unit test all use placeholder/fake terms or path-based references only." This is enforced both by the hook and by reviewer discipline; the fake term `"fake-denylisted-term-for-test"` is the recommended placeholder for the test.

## No Analog Found

No phase-7 file lacks an analog. Every file maps cleanly to an existing pattern in the codebase or planning tree:

- `verify_public_repo.py` -> `check_public_discipline.py` (the same author wrote both for the same purpose; the new script is a sibling, not an independent design)
- `test_check_public_discipline.py` -> three test analogs (parametrize shape, monkeypatch shape, case-table shape) all already in `tests/unit/`
- `07-FINDINGS.md` -> `.planning/phases/audit/findings.md` (the explicit precedent named in CONTEXT.md D-10)
- `Makefile` change -> existing one-line `uv run` wrapper targets (3 close analogs)
- `README.md` change -> existing numbered-step setup block
- `REQUIREMENTS.md` change -> 15 existing Complete-row precedents in the same table

## Metadata

**Analog search scope:** `scripts/`, `tests/unit/`, `.planning/phases/`, `Makefile`, `README.md`, `.planning/REQUIREMENTS.md`, `.pre-commit-config.yaml`
**Files scanned:** ~15 (see analog list above; targeted reads only)
**Pattern extraction date:** 2026-05-23
