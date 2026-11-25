# Development

Needs Python 3.13 or later.

    python -m venv .venv
    .venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -e "server[dev]"

Checks, all run by CI:

    ruff check .
    pytest server/tests
    python scripts/rule_coverage.py
    python scripts/docs_check.py
    python scripts/version_check.py

The integration tests need Python 3.14 and Linux (or CI):

    pip install pytest-homeassistant-custom-component
    pip install -e server
    python -m pytest ha_tests -o asyncio_mode=auto

To redraw the logo: `pip install pillow`, then `python scripts/make_brand.py BOLD_FONT.ttf`.

`rule_coverage.py` reports hard rules without a tagged test and, with `--release`, fails if any remain. It cannot judge whether a test truly proves its rule; reviewers must. See [Safety rules](../HARD_RULES.md).
