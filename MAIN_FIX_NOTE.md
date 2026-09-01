# Main branch pipeline fix

This file documents the direct repair applied on the integration branch before merging to `main`.

- Canonical pipeline: `iea/pipeline.py`
- Scheduler: `iea/scheduler.py`
- Root `pipeline.py` is a compatibility wrapper.
- The pipeline reads `config/series.yaml`, uses `FRED`, `BLS`, and `Store`, and persists observations to `IEA_DB_PATH`.
