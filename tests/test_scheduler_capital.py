import pytest

from iea.scheduler import _capital_from_environment


def test_capital_from_environment_is_optional(monkeypatch):
    monkeypatch.delenv("IEA_CAPITAL", raising=False)
    assert _capital_from_environment() is None


def test_capital_from_environment_parses_numeric_value(monkeypatch):
    monkeypatch.setenv("IEA_CAPITAL", "100000000")
    assert _capital_from_environment() == 100000000.0


def test_capital_from_environment_rejects_invalid_value(monkeypatch):
    monkeypatch.setenv("IEA_CAPITAL", "not-a-number")
    with pytest.raises(ValueError, match="IEA_CAPITAL must be a numeric value"):
        _capital_from_environment()


def test_capital_from_environment_rejects_negative_value(monkeypatch):
    monkeypatch.setenv("IEA_CAPITAL", "-1")
    with pytest.raises(ValueError, match="IEA_CAPITAL must be non-negative"):
        _capital_from_environment()
