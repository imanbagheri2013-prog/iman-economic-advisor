"""Compatibility wrapper for the canonical IEA ingestion pipeline."""

from iea.pipeline import load_config, pull, pull_and_check

__all__ = ["load_config", "pull", "pull_and_check"]
