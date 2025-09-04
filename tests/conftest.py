import pytest


def pytest_configure(config: pytest.Config) -> None:
    # Ensure custom markers are always registered, even if pytest.ini isn't parsed
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "slow: marks tests as slow tests")

