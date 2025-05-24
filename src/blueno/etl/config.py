from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

import polars as pl
from polars.datatypes.classes import DataTypeClass

from blueno.utils import character_translation, to_snake_case


@dataclass
class IncrementalColumn:
    """Represents an incremental column in the configuration.

    Attributes:
        name: The name of the incremental column.
        data_type: The data type of the incremental column.

    Example:
    ```python
    from blueno.etl import IncrementalColumn
    import polars as pl

    incremental_column = IncrementalColumn("batch_id", pl.Int64)
    ```
    """

    name: str
    data_type: DataTypeClass


@dataclass(kw_only=True)
class KeyColumn:
    """Represents a key column in the configuration.

    Attributes:
        prefix: The prefix of the key column.
        suffix: The suffix of the key column.
        data_type: The data type of the key column.
        default_value: The default value the key column.

    Example:
    Key column with suffix
    ```python
    from blueno.etl.config import KeyColumn
    import polars as pl

    key_column = KeyColumn(suffix="_sk", data_type=pl.Int64, default_value=pl.lit(1))
    ```

    Key column with prefix
    ```python
    from blueno.etl.config import KeyColumn
    import polars as pl

    key_column = KeyColumn(prefix="PK_", data_type=pl.Int64, default_value=pl.lit(1))
    ```
    """

    prefix: Optional[str] = None
    suffix: Optional[str] = None
    data_type: Optional[DataTypeClass] = None
    default_value: Optional[pl.Expr] = None

    def __post_init__(self):
        """Ensures that at least one of prefix and suffixs are provided."""
        if self.prefix is None and self.suffix is None:
            raise ValueError("At least one of prefix or suffix must be provided")


@dataclass
class Column:
    """Represents an audit column in the configuration.

    Attributes:
        name: The name of the audit column.
        default_value: The default value expression for the audit column.

    Example:
    ```python
    from blueno.etl.config import Column
    import polars as pl
    from datetime import datetime, timezone

    audit_column = Column(
        "__created_at", pl.lit(datetime.now(timezone.utc)).cast(pl.Datetime("us", "UTC"))
    )
    ```
    """

    name: str
    default_value: pl.Expr


@dataclass()
class Config:
    """Configuration class that holds various columns and their properties.

    Attributes:
        incremental_column: The incremental column configuration.
        column_created_at: The created at audit column configuration.
        column_modified_at: The modified at audit column configuration.
        column_deleted_at: The deleted at audit column configuration.
        column_valid_from: The valid from audit column configuration.
        column_valid_to: The valid to audit column configuration.
        character_translation_map: A mapping of special characters to their translations.
        normalization_strategy: A function that takes a column name and returns the normalized name.
    """

    surrogate_key_column: KeyColumn
    historical_surrogate_key_calendar_column_base_name: str
    historical_surrogate_key_column: KeyColumn
    business_key_column: KeyColumn
    composite_key_column: KeyColumn

    incremental_column: IncrementalColumn
    column_created_at: Column
    column_modified_at: Column
    column_deleted_at: Column
    column_valid_from: Column
    column_valid_to: Column
    character_translation_map: dict[str, str]
    normalization_strategy: Callable[[str], str]

    def __init__(self):
        """Creates a Config."""
        self.surrogate_key_column = KeyColumn(
            suffix="_sk", data_type=pl.Int64, default_value=pl.lit(-1)
        )
        self.historical_surrogate_key_calendar_column_base_name = "calendar"
        self.historical_surrogate_key_column = KeyColumn(
            suffix="_hsk", data_type=pl.Int64, default_value=pl.lit(-1)
        )
        self.business_key_column = KeyColumn(suffix="_bk")
        self.composite_key_column = KeyColumn(suffix="_ck")

        # TODO: Change to `__run_id`
        self.incremental_column = IncrementalColumn("batch_id", pl.Int64)
        self.column_created_at = Column(
            "__created_at", pl.lit(datetime.now(timezone.utc)).cast(pl.Datetime("us", "UTC"))
        )
        self.column_modified_at = Column(
            "__modified_at", pl.lit(datetime.now(timezone.utc)).cast(pl.Datetime("us", "UTC"))
        )
        self.column_deleted_at = Column("__deleted_at", pl.lit(None).cast(pl.Datetime("us", "UTC")))
        self.column_valid_from = Column(
            "__valid_from", pl.lit(datetime.now(timezone.utc)).cast(pl.Datetime("us", "UTC"))
        )
        self.column_valid_to = Column("__valid_to", pl.lit(None).cast(pl.Datetime("us", "UTC")))
        self.character_translation_map = {
            " ": "_",
            "-": "_",
            "'": "_",
            '"': "_",
            "(": "_",
            ")": "_",
            ",": "_",
            ".": "_",
            ":": "_",
            ";": "_",
            "!": "_",
            "?": "_",
            "|": "_or",
            "[": "_",
            "]": "_",
            "{": "_",
            "}": "_",
            "&": "_and",
            "/": "_or",
            "\\": "_or",
            "%": "_percent",
            "+": "_plus",
            "*": "_times",
            "=": "_equals",
            "<": "_lt",
            ">": "_gt",
            "@": "_at",
            "$": "_dollar",
            "~": "_approximate",
        }
        self.normalization_strategy = lambda name: to_snake_case(
            character_translation(name, self.character_translation_map)
        )

    def get_static_audit_columns(self) -> list[Column]:
        """Returns a list of static audit columns, namely the `created_at` and `valid_from` columns.

        Returns:
            A list containing the static audit columns.

        Example:
        ```python
        from blueno.etl.config import get_default_config

        config = get_default_config()

        static_columns = config.get_static_audit_columns()
        ```
        """
        return [
            self.column_created_at,
            self.column_valid_from,
        ]

    def get_dynamic_audit_columns(self) -> list[Column]:
        """Returns a list of dynamic audit columns, namely the `modified_at` and `valid_to` columns.

        Returns:
            A list containing the dynamic audit columns.

        Example:
        ```python
        from blueno.etl.config import get_default_config

        config = get_default_config()

        dynamic_columns = config.get_dynamic_audit_columns()
        ```
        """
        return [
            self.column_modified_at,
            self.column_valid_to,
            self.column_deleted_at,
        ]

    def get_audit_columns(self) -> list[Column]:
        """Returns a list of all audit columns, namely the `created_at`, `modified_at`, `valid_from`, and `valid_to` columns.

        Returns:
            A list containing all audit columns.

        Example:
        ```python
        from blueno.etl.config import get_default_config

        config = get_default_config()

        all_columns = config.get_audit_columns()
        ```
        """
        return [
            self.column_created_at,
            self.column_modified_at,
            self.column_deleted_at,
            self.column_valid_from,
            self.column_valid_to,
        ]


def create_config(
    incremental_column: IncrementalColumn,
    created_at: Column,
    modified_at: Column,
    deleted_at: Column,
    valid_from: Column,
    valid_to: Column,
) -> Config:
    """Creates a new Config instance with the provided audit and incremental columns.

    Args:
        incremental_column: The incremental column.
        created_at: The created at audit column.
        modified_at: The modified at audit column.
        deleted_at: The deleted at audit column.
        valid_from: The valid from audit column.
        valid_to: The valid to audit column.

    Returns:
        A new instance of the Config class.

    Example:
    ```python
    from blueno.etl.config import IncrementalColumn, Column, create_config
    import polars as pl
    from datetime import datetime, timezone

    incremental_column = IncrementalColumn("batch_id", pl.Int64)
    created_at = Column(
        "__created_at", pl.lit(datetime.now(timezone.utc)).cast(pl.Datetime("us", "UTC"))
    )
    modified_at = Column(
        "__modified_at", pl.lit(datetime.now(timezone.utc)).cast(pl.Datetime("us", "UTC"))
    )
    deleted_at = Column(
        "__deleted_at", pl.lit(datetime.now(timezone.utc)).cast(pl.Datetime("us", "UTC"))
    )
    valid_from = Column(
        "__valid_from", pl.lit(datetime.now(timezone.utc)).cast(pl.Datetime("us", "UTC"))
    )
    valid_to = Column(
        "__valid_to", pl.lit(datetime.now(timezone.utc)).cast(pl.Datetime("us", "UTC"))
    )

    config = create_config(
        incremental_column,
        created_at,
        modified_at,
        deleted_at,
        valid_from,
        valid_to,
    )
    ```
    """
    config = Config()
    config.incremental_column = incremental_column
    config.column_created_at = created_at
    config.column_modified_at = modified_at
    config.column_deleted_at = deleted_at
    config.column_valid_from = valid_from
    config.column_valid_to = valid_to

    return config


def get_default_config() -> Config:
    """Returns a default Config instance with preset values.

    Returns:
        A default instance of the Config class.

    Example:
    ```python
    from blueno.etl.config import get_default_config

    default_config = get_default_config()
    ```
    """
    return Config()
