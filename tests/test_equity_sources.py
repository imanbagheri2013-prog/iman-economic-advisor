from __future__ import annotations

from iea.equity_sources import fetch_live_equity_input


def test_fetch_live_equity_input_uses_sec_and_stooq(monkeypatch):
    tickers = {"0": {"ticker": "TEST", "cik_str": 12345}}
    facts = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {"USD": {"units": [
                    {"val": 1200, "form": "10-K", "end": "2025-12-31", "filed": "2026-02-01"},
                    {"val": 1000, "form": "10-K", "end": "2024-12-31", "filed": "2025-02-01"},
                ]}},
                "GrossProfit": {"USD": {"units": [{"val": 480, "form": "10-K", "end": "2025-12-31", "filed": "2026-02-01"}]}},
                "OperatingIncomeLoss": {"USD": {"units": [{"val": 240, "form": "10-K", "end": "2025-12-31", "filed": "2026-02-01"}]}},
                "NetIncomeLoss": {"USD": {"units": [
                    {"val": 144, "form": "10-K", "end": "2025-12-31", "filed": "2026-02-01"},
                    {"val": 120, "form": "10-K", "end": "2024-12-31", "filed": "2025-02-01"},
                ]}},
                "NetCashProvidedByUsedInOperatingActivities": {"USD": {"units": [{"val": 200, "form": "10-K", "end": "2025-12-31", "filed": "2026-02-01"}]}},
                "PaymentsToAcquirePropertyPlantAndEquipment": {"USD": {"units": [{"val": 60, "form": "10-K", "end": "2025-12-31", "filed": "2026-02-01"}]}},
                "LongTermDebtNoncurrent": {"USD": {"units": [{"val": 150, "form": "10-K", "end": "2025-12-31", "filed": "2026-02-01"}]}},
                "CashAndCashEquivalentsAtCarryingValue": {"USD": {"units": [{"val": 100, "form": "10-K", "end": "2025-12-31", "filed": "2026-02-01"}]}},
                "StockholdersEquity": {"USD": {"units": [{"val": 800, "form": "10-K", "end": "2025-12-31", "filed": "2026-02-01"}]}},
                "EntityCommonStockSharesOutstanding": {"shares": {"units": [{"val": 100, "form": "10-K", "end": "2025-12-31", "filed": "2026-02-01"}]}},
            }
        }
    }

    def fake_json(url, timeout):
        return tickers if "company_tickers" in url else facts

    class Response:
        text = "Symbol,Date,Time,Open,High,Low,Close,Volume\nTEST.US,2026-09-05,00:00:00,10,11,9,10,1000\n"
        def raise_for_status(self):
            return None

    monkeypatch.setattr("iea.equity_sources._get_json", fake_json)
    monkeypatch.setattr("iea.equity_sources.requests.get", lambda *args, **kwargs: Response())
    monkeypatch.setenv("IEA_EQUITY_PE_MULTIPLE", "15")

    result = fetch_live_equity_input("TEST")

    assert result.source == "SEC_COMPANYFACTS+STOOQ"
    assert result.current_price == 10
    assert result.snapshot.revenue == 1200
    assert result.snapshot.prior_revenue == 1000
    assert result.snapshot.net_profit == 144
    assert result.snapshot.shares_outstanding == 100
    assert result.method_values == (21.6,)
    assert result.method_weights == (1.0,)
