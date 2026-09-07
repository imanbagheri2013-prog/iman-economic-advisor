#!/bin/sh
set -eu

export IEA_API_HOST="0.0.0.0"
export IEA_API_PORT="${PORT:-8000}"
export IEA_REPORT_PATH="${IEA_REPORT_PATH:-/data/health_report.json}"

exec iea-api
