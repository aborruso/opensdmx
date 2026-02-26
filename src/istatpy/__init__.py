"""istatpy — Python interface to the ISTAT SDMX REST API."""

from .base import istat_timeout
from .discovery import (
    all_available,
    dimensions_info,
    get_available_values,
    get_dimension_values,
    istat_dataset,
    print_dataset,
    reset_filters,
    search_dataset,
    set_filters,
)
from .retrieval import get_data, istat_get, parse_time_period
from .cli import main

__all__ = [
    "all_available",
    "search_dataset",
    "istat_dataset",
    "print_dataset",
    "dimensions_info",
    "get_dimension_values",
    "get_available_values",
    "set_filters",
    "reset_filters",
    "get_data",
    "istat_get",
    "istat_timeout",
    "parse_time_period",
]
