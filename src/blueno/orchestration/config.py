from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import polars as pl


@dataclass
class Config:
    """Configuration class for Blueno orchestration.

    This singleton class manages configuration settings for column naming and default values
    used in data orchestration. It handles:
    - Identity column naming conventions
    - Temporal validity columns (valid_from, valid_to)
    - Metadata columns (created_at, modified_at)
    - Current record tracking

    All properties are read-only and initialized with default values.
    """

    _instance: Optional[Config] = None

    def __new__(cls):
        """Singleton method."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._initialize_defaults(cls)
        return cls._instance

    def _initialize_defaults(self):
        self._identity_column_prefix = "sk_"
        self._identity_colunn_suffix = None
        self._identity_column_name = (
            (self._identity_column_prefix or "")
            + "{blueprint_name}"
            + (self._identity_colunn_suffix or "")
        )
        self._valid_from_column = "_bl_valid_from"
        self._valid_from_default_value = pl.lit(datetime(1970, 1, 1)).cast(pl.Datetime("us", "UTC"))
        self._valid_to_column = "_bl_valid_to"
        self._valid_to_default_value = pl.lit(None).cast(pl.Datetime("us", "UTC"))
        self._created_at_column = "_bl_created_at"
        self._created_at_default_value = pl.lit(datetime.now(timezone.utc)).cast(
            pl.Datetime("us", "UTC")
        )
        self._modified_at_column = "_bl_modified_at"
        self._modified_at_default_value = pl.lit(datetime.now(timezone.utc)).cast(
            pl.Datetime("us", "UTC")
        )
        self._is_current_column = "_bl_is_current"
        self._is_current_default_value = pl.lit(True)

    @property
    def identity_column_prefix(self) -> Optional[str]:
        """Get the prefix used for identity columns.

        Returns:
            str: The configured identity column prefix
        """
        return self._identity_column_prefix

    @property
    def identity_column_suffix(self) -> Optional[str]:
        """Get the suffix used for identity columns.

        Returns:
            Optional[str]: The configured identity column suffix, if any
        """
        return self._identity_colunn_suffix

    @property
    def identity_column_name(self) -> str:
        """Get the template for identity column names.

        Returns:
            str: The identity column name template
        """
        return self._identity_column_name

    @property
    def valid_from_column(self) -> str:
        """Get the name of the valid_from column.

        Returns:
            str: The valid_from column name
        """
        return self._valid_from_column

    @property
    def valid_from_default_value(self) -> pl.Expr:
        """Get the default value for valid_from column.

        Returns:
            pl.Expr: Polars expression for the default valid_from value
        """
        return self._valid_from_default_value

    @property
    def valid_to_column(self) -> str:
        """Get the name of the valid_to column.

        Returns:
            str: The valid_to column name
        """
        return self._valid_to_column

    @property
    def valid_to_default_value(self) -> pl.Expr:
        """Get the default value for valid_to column.

        Returns:
            pl.Expr: Polars expression for the default valid_to value
        """
        return self._valid_to_default_value

    @property
    def created_at_column(self) -> str:
        """Get the name of the created_at column.

        Returns:
            str: The created_at column name
        """
        return self._created_at_column

    @property
    def created_at_default_value(self) -> pl.Expr:
        """Get the default value for created_at column.

        Returns:
            pl.Expr: Polars expression for the default created_at value
        """
        return self._created_at_default_value

    @property
    def modified_at_column(self) -> str:
        """Get the name of the modified_at column.

        Returns:
            str: The modified_at column name
        """
        return self._modified_at_column

    @property
    def modified_at_default_value(self) -> pl.Expr:
        """Get the default value for modified_at column.

        Returns:
            pl.Expr: Polars expression for the default modified_at value
        """
        return self._modified_at_default_value

    @property
    def is_current_column(self) -> str:
        """Get the name of the is_current column.

        Returns:
            str: The is_current column name
        """
        return self._is_current_column

    @property
    def is_current_default_value(self) -> pl.Expr:
        """Get the default value for is_current column.

        Returns:
            pl.Expr: Polars expression for the default is_current value
        """
        return self._is_current_default_value


def get_config() -> Config:
    """Returns a Config instance with preset values.

    Returns:
        A instance of the Config class.

    Example:
    ```python
    from blueno.orchestration.config import get_config

    default_config = get_config()
    ```
    """
    return Config()
