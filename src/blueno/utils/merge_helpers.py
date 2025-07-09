"""A collection of string builder functions for merging."""

from blueno.utils import quote_identifier


def build_merge_predicate(
    columns: list[str], source_alias: str = "source", target_alias: str = "target"
) -> str:
    """Constructs a SQL merge predicate based on the provided column names.

    This function generates a string that represents the condition for merging
    records based on equality of the specified columns.

    Args:
        columns: A list of column names to be used in the merge predicate.
        source_alias: An alias for the source
        target_alias: An alias for the target

    Returns:
        A SQL string representing the merge predicate.

    Example:
    ```python
    from blueno.utils import build_merge_predicate

    predicate = build_merge_predicate(['id', 'name'])
    print(predicate)
    \"\"\"
        (target."id" = source."id") AND (target."name" = source."name")
    \"\"\"
    ```
    """
    merge_predicate = [
        f"""
            ({target_alias}.{quote_identifier(column)} = {source_alias}.{quote_identifier(column)})
        """
        for column in columns
    ]
    return " AND ".join(merge_predicate)


def build_when_matched_update_predicate(
    existing_columns: list[str],
    new_columns: list[str] | None = None,
    source_alias: str = "source",
    target_alias: str = "target",
) -> str:
    """Constructs a SQL predicate for when matched update conditions.

    This function generates a string that represents the conditions for updating
    records when a match is found based on the specified columns.

    Args:
        existing_columns: A list of column names to be used in the update predicate. These columns must existing both source and target dataframe.
        new_columns: A list of columns only existing in the source.
        source_alias: An alias for the source
        target_alias: An alias for the target

    Returns:
        A SQL string representing the when matched update predicate.

    Example:
    ```python
    from blueno.utils import build_when_matched_update_predicate

    update_predicate = build_when_matched_update_predicate(['id', 'status'])
    print(update_predicate)
    \"\"\"
        (
            (target."id" != source."id")
            OR (target."id" IS NULL AND source."id" IS NOT NULL)
            OR (target."id" IS NOT NULL AND source."id" IS NULL)
        ) OR ...
    \"\"\"
    ```
    """
    when_matched_update_predicates = [
        f"""
            (
                ({target_alias}.{quote_identifier(column)} != {source_alias}.{quote_identifier(column)})
                OR ({target_alias}.{quote_identifier(column)} IS NULL AND {source_alias}.{quote_identifier(column)} IS NOT NULL)
                OR ({target_alias}.{quote_identifier(column)} IS NOT NULL AND {source_alias}.{quote_identifier(column)} IS NULL)
            )
        """
        for column in existing_columns
    ]

    when_matched_update_predicate = " OR ".join(when_matched_update_predicates)

    if new_columns:
        when_matched_update_predicate += " OR "
        when_matched_update_predicate += " OR ".join(
            [
                f"""
                    ({source_alias}.{quote_identifier(column)} IS NOT NULL)
                """
                for column in new_columns
            ]
        )

    return when_matched_update_predicate


def build_when_matched_update_columns(
    columns: list[str], source_alias: str = "source", target_alias: str = "target"
) -> dict[str, str]:
    """Constructs a mapping of columns to be updated when a match is found.

    This function generates a dictionary where the keys are the target column
    names and the values are the corresponding source column names.

    Args:
        columns: A list of column names to be used in the update mapping.
        source_alias: An alias for the source
        target_alias: An alias for the target

    Returns:
        A dictionary mapping target columns to source columns.

    Example:
    ```python
    from blueno.utils import build_when_matched_update_columns

    update_columns = build_when_matched_update_columns(["id", "name"])
    print(update_columns)

    {'target."id"': 'source."id"', 'target."name"': 'source."name"'}
    ```
    """
    return {
        f"{target_alias}.{quote_identifier(column)}": f"{source_alias}.{quote_identifier(column)}"
        for column in columns
    }
