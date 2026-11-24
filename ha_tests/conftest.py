import pytest


@pytest.fixture(autouse=True)
def _custom(enable_custom_integrations):
    yield
