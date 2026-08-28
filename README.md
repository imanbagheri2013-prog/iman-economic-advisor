# IEA Data Engine v1.2
Real-data ingestion foundation for Iman Economic Advisor.

Includes FRED and BLS adapters, normalized observations, quality/freshness scoring,
SQLite storage, configurable series registry, provider interfaces for market/crypto/Iran/geopolitics,
health reporting, tests and GitHub Actions CI.

Setup:
1. python -m venv .venv
2. activate it
3. pip install -r requirements.txt
4. copy .env.example .env
5. add FRED_API_KEY
6. python -m iea.cli health
7. python -m iea.cli pull
8. python -m iea.cli report

Never commit API keys.
