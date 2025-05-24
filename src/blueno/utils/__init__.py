"""Collection of utility functions."""

from blueno.utils.quote_identifier import quote_identifier

from .get_max_column_value import get_max_column_value
from .get_min_column_value import get_min_column_value
from .get_or_create_delta_table import get_or_create_delta_table
from .merge_helpers import (
    build_merge_predicate,
    build_when_matched_update_columns,
    build_when_matched_update_predicate,
)
from .separator_indices import separator_indices
from .string_normalization import character_translation, to_snake_case

__all__ = (
    "separator_indices",
    "quote_identifier",
    "to_snake_case",
    "character_translation",
    "merge_helpers",
    "quote_identifier",
    "remove_none",
    "get_or_create_delta_table",
    "build_merge_predicate",
    "build_when_matched_update_predicate",
    "build_when_matched_update_columns",
    "get_min_column_value",
    "get_max_column_value",
)
