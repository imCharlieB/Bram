# Working on BRAM

- [HARD_RULES.md](HARD_RULES.md) overrides everything, then [SPEC.md](SPEC.md). Changing either needs owner approval.
- Each milestone needs owner approval before the next starts.
- Nothing house-specific (names, entity IDs, addresses) in code, tests, or user docs. Site details belong in `private/`, which Git ignores.
- A test that proves a hard rule is tagged `@pytest.mark.rule("ID")`. Tag only tests that truly prove it.

## Done means documented

In the same change:
- user-visible behavior, settings, or commands: update `docs/` and, if it affects getting started, `README.md`
- anything a user would notice: add a line under Unreleased in `CHANGELOG.md`
- what works and what does not: keep the README status table honest

## Checks

    ruff check .
    pytest server/tests
    python scripts/rule_coverage.py
    python scripts/docs_check.py
