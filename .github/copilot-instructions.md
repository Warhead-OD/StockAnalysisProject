# Local Copilot Working Rules (Do Not Commit)

Purpose: enforce user-specific collaboration rules plus repository conventions for all GitHub Copilot chats in this workspace.

## User Collaboration Rules

- Deliver changes in very small, commit-sized slices.
- Hard commit size limit: target 30-100 lines changed per commit (additions + deletions). If a slice exceeds this range, split it into additional commits.
- Keep API code and test code in separate commits whenever feasible.
- Enforce strict semantic commit splits for every slice. Use exactly one of these commit types per commit:
  - feat: new user-facing or reusable functionality
  - fix: bug fix only
  - docs: documentation-only changes
  - style: formatting/style-only changes with no logic changes
  - refactor: internal code restructuring with no behavior change
  - test: test-only changes
  - chore: tooling/maintenance/non-feature housekeeping
- Never mix semantic commit categories in one commit. If changes cross categories, split them into separate commits.
- Run tests before proposing each commit.
- After each test run, report results and pause for user approval before continuing to the next slice.
- Provide an explicit semantic release recommendation for each slice:
  - patch: wiring, refactors, tests, bug fixes, no new public API
  - minor: new reusable/public API surface
- Prefer incremental, reversible changes over large rewrites.

## Architecture and Design Patterns (Current Codebase)

- Keep CLI thin:
  - `src/cli/main.py` should orchestrate I/O, argument handling, and user messages.
  - Business logic belongs in reusable modules, not command handlers.
- Use workflow facades for command-level orchestration:
  - `analysis.run_analyze_workflow(...)`
  - `analysis.run_build_strategy_workflow(...)`
- Preserve layering:
  - `src/data`: repositories, market/session cache access
  - `src/analysis`: strategy building, metrics, refinement, workflows
  - `src/cli`: adapters only
- Favor dependency injection through function parameters for external modules/services (market access, repositories, builders).
- Maintain deterministic artifact contracts and file paths:
  - strategy artifacts in `outputs/strategy_plan_<TICKER>_<INTERVAL>.json`
  - thinkscript exports in `outputs/thinkscript_<TICKER>_<INTERVAL>_<MODE>.txt`
  - market artifacts under `downloads/market` and `downloads/meta`
- Keep merge/date behavior consistent:
  - normalize date columns before metric/refinement workflows
  - use interval-aware date normalization utilities
- Preserve robust CLI error semantics:
  - validation/load errors should print to stderr and exit non-zero
  - non-fatal refinement issues may be logged as skipped behavior when metrics can still be produced

## Coding Conventions

- Python conventions:
  - use type hints on public functions and workflow APIs
  - keep function names explicit and verb-first (`run_*`, `resolve_*`, `save_*`, `load_*`)
  - use small, composable functions over monolithic handlers
- DataFrame conventions:
  - prefer normalized lowercase columns (`date`, `open`, `high`, `low`, `close`, `adj_close`, `volume`)
  - make joins and derived calculations explicit and testable
- Testing conventions:
  - use pytest and monkeypatch for isolation
  - add focused tests for each new reusable API
  - keep CLI tests focused on delegation, command routing, output/error behavior

## Tooling, Hooks, and Subagents Policy

Use supporting automation when it increases code quality and confidence.

- Tools are allowed and encouraged for:
  - targeted file/code search
  - safe refactoring and patch application
  - repeatable test execution
  - validation before commit handoff
- Subagents are permitted for:
  - read-only architecture/codebase exploration
  - broad pattern discovery in large code regions
  - collecting candidates for refactor slices
- Hooks are permitted for deterministic quality gates, including:
  - pre-tool or pre-commit style checks
  - formatting/lint/test commands
  - blocking unsafe operations when configured

## Safety and Scope Controls

- Do not introduce unrelated refactors in the same slice.
- Do not silently change artifact naming contracts.
- Do not bypass test gates for modified behavior.
- If the workspace contains unexpected unrelated changes, stop and ask before proceeding.

## Suggested Slice Hand-off Format

For each slice, provide:

1. What changed (API/test/CLI wiring)
2. Tests run and pass/fail counts
3. Proposed commit message
4. Release action (patch/minor) with one-line rationale
5. Wait for user approval before next slice
