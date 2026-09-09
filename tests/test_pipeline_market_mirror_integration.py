from pathlib import Path
from unittest.mock import Mock, patch

from iea import pipeline


def _config():
    return {
        "closed_dates": [],
        "iran_market_mirror_url": "https://example.test/iran_market_live.json",
        "iran_symbols": ["فولاد", "فملی"],
    }


def test_pipeline_integrates_market_mirror_health_into_overall_status():
    store = Mock()
    freshness = {"component": "macro", "status": "HEALTHY"}
    mirror = {
        "component": "iran_market_mirror",
        "status": "CRITICAL",
        "valid_symbol_count": 0,
        "analysis_ready_symbol_count": 0,
    }

    with (
        patch.object(pipeline, "load_config", return_value=_config()),
        patch.object(pipeline, "pull", return_value=store),
        patch.object(pipeline, "check_table_freshness", return_value=freshness),
        patch.object(pipeline, "check_market_mirror_health", return_value=mirror) as health_check,
    ):
        returned_store, results, status = pipeline.pull_and_check()

    assert returned_store is store
    assert results == [freshness, mirror]
    assert status == "CRITICAL"
    health_check.assert_called_once_with(
        "https://example.test/iran_market_live.json",
        expected_symbols=["فولاد", "فملی"],
    )


def test_pipeline_keeps_market_mirror_warning_non_critical():
    store = Mock()
    freshness = {"component": "macro", "status": "HEALTHY"}
    mirror = {
        "component": "iran_market_mirror",
        "status": "WARNING",
        "valid_symbol_count": 2,
        "analysis_ready_symbol_count": 1,
    }

    with (
        patch.object(pipeline, "load_config", return_value=_config()),
        patch.object(pipeline, "pull", return_value=store),
        patch.object(pipeline, "check_table_freshness", return_value=freshness),
        patch.object(pipeline, "check_market_mirror_health", return_value=mirror),
    ):
        returned_store, results, status = pipeline.pull_and_check()

    assert returned_store is store
    assert results == [freshness, mirror]
    assert status == "OK"


def test_pipeline_skips_mirror_check_when_no_iran_symbols_are_configured():
    store = Mock()
    config = {
        "closed_dates": [],
        "iran_market_mirror_url": "https://example.test/iran_market_live.json",
        "iran_symbols": [],
    }
    freshness = {"component": "macro", "status": "HEALTHY"}

    with (
        patch.object(pipeline, "load_config", return_value=config),
        patch.object(pipeline, "pull", return_value=store),
        patch.object(pipeline, "check_table_freshness", return_value=freshness),
        patch.object(pipeline, "check_market_mirror_health") as health_check,
    ):
        returned_store, results, status = pipeline.pull_and_check()

    assert returned_store is store
    assert results == [freshness]
    assert status == "OK"
    health_check.assert_not_called()
