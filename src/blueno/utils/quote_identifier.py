def quote_identifier(identifier: str, quote_character: str = '"') -> str:
    """Quotes the given identifier by surrounding it with the specified quote character.

    Args:
        identifier: The identifier to be quoted.
        quote_character: The character to use for quoting. Defaults to '"'.

    Returns:
        The quoted identifier.

    Example:
    ```python
    from blueno.utils import quote_identifier

    quote_identifier("my_object")
    '"my_object"'
    quote_identifier("my_object", "'")
    "'my_object'"
    ```
    """
    return f"{quote_character}{identifier.strip(quote_character)}{quote_character}"
