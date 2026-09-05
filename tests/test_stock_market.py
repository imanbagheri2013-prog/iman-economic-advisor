import pytest

from iea.stock_market import StockSnapshot, rank_stocks, score_stock, stock_market_summary


def test_stock_score_detects_undervaluation_and_quality():
    score = score_stock(StockSnapshot("فولاد", 100), fair_value=130, quality_score=0.8)
    assert score.symbol == "فولاد"
    assert score.valuation_signal == "UNDERVALUED"
    assert score.quality_signal == "STRONG"
    assert score.score == 87.0


def test_stock_ranking_and_summary():
    weak = score_stock(StockSnapshot("A", 100), fair_value=90, quality_score=0.4)
    strong = score_stock(StockSnapshot("B", 100), fair_value=130, quality_score=0.8)
    ranked = rank_stocks([weak, strong])
    assert [item.symbol for item in ranked] == ["B", "A"]
    summary = stock_market_summary([weak, strong])
    assert summary["universe_size"] == 2
    assert summary["top_candidates"][0]["symbol"] == "B"


def test_unavailable_valuation_is_penalized():
    score = score_stock(StockSnapshot("A", 100), quality_score=0.5)
    assert score.valuation_signal == "UNAVAILABLE"
    assert score.score == 40.0


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        score_stock(StockSnapshot("A", 0))
    with pytest.raises(ValueError):
        score_stock(StockSnapshot("A", 100), quality_score=1.1)
