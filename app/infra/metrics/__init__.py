"""Metrics collection module for Prometheus."""

from app.infra.metrics.service import MetricsService, get_metrics

__all__ = [
    "MetricsService",
    "get_metrics",
]
