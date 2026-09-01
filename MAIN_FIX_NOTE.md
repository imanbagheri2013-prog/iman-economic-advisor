# Main branch pipeline fix

- Canonical pipeline: `iea/pipeline.py`
- Scheduler: `iea/scheduler.py`
- Root `pipeline.py` is a compatibility wrapper.
- The pipeline reads `config/series.yaml`, uses `FRED`, `BLS`, and `Store`, and persists observations to `IEA_DB_PATH`.
