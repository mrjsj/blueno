"""Collection of utility functions."""

from blueno.utils.misc import quote_identifier, remove_none, separator_indices, shorten_dict_values

from .delta import (
    get_last_modified_time,
    get_max_column_value,
    get_min_column_value,
    get_or_create_delta_table,
)
from .merge_helpers import (
    build_merge_predicate,
    build_when_matched_update_columns,
    build_when_matched_update_predicate,
)
from .string_normalization import character_translation, to_snake_case

__all__ = (
    "get_last_modified_time",
    "get_or_create_delta_table",
    "separator_indices",
    "quote_identifier",
    "to_snake_case",
    "character_translation",
    "merge_helpers",
    "quote_identifier",
    "remove_none",
    "shorten_dict_values",
    "build_merge_predicate",
    "build_when_matched_update_predicate",
    "build_when_matched_update_columns",
    "get_min_column_value",
    "get_max_column_value",
)
