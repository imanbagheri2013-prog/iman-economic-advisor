# Production deployment on Railway

The repository is Railway-ready and uses the root `Dockerfile` for the API service.

## API service

- Build: root `Dockerfile`
- Health check: `/health`
- Port: Railway injects `PORT`; the application uses it automatically.
- Report path: set `IEA_REPORT_PATH=/data/health_report.json` when a shared runtime volume is available.
- Recommended restart policy: on failure.

## Scheduler / data worker

The scheduler must run separately from the API process. It should write the trusted `health_report.json` into the same persistent volume used by the API. The repository includes `iea.production_worker` for this purpose.

Do not expose secrets in repository files. Configure FRED/BLS/CBI credentials and URLs as Railway environment variables/secrets.

## Important

A container image alone does not make the advisor live: the API needs a current trusted report. Deploy the API and scheduler as separate services that share persistent storage, or provide the report through another trusted runtime storage mechanism.
