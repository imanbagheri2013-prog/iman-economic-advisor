# IEA Core v1.1 — Real Data Engine
Production-oriented data foundation for Iman Economic Advisor.

Includes FRED + BLS adapters, normalized observations, quality/freshness scoring,
SQLite storage, configurable series registry, pull pipeline, health report,
tests and GitHub Actions CI.

Quick start:
1. python -m venv .venv
2. activate the environment
3. pip install -r requirements.txt
4. copy .env.example .env
5. put your FRED API key in .env
6. python -m iea.cli health
7. python -m iea.cli pull
8. python -m iea.cli report

Never commit API keys.
