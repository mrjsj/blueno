from typing import Dict, List, Union


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


def remove_none(obj: Union[Dict, List]) -> Union[Dict, List]:
    """Recursively remove None values from dictionaries and lists.

    Args:
        obj: The data structure to clean.

    Returns:
        A new data structure with None values removed.
    """
    if isinstance(obj, dict):
        return {k: remove_none(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [remove_none(item) for item in obj if item is not None]
    else:
        return obj


def separator_indices(string: str, separator: str) -> list[int]:
    """Find indices of a separator character in a string, ignoring separators inside quotes.

    Args:
        string: The input string to search through
        separator: The separator character to find

    Returns:
        A list of indices where the separator character appears outside of quotes

    Example:
    ```python
    from blueno.utils import separator_indices

    separator_indices('a,b,"c,d",e', ",")
    [1, 8]
    ```
    """
    inside_double_quotes = False
    inside_single_quotes = False
    indices = []

    for idx, char in enumerate(string):
        if char == '"' and not inside_single_quotes:
            inside_double_quotes = not inside_double_quotes
        elif char == "'" and not inside_double_quotes:
            inside_single_quotes = not inside_single_quotes
        elif inside_double_quotes or inside_single_quotes:
            continue
        elif char == separator:
            indices.append(idx)

    return indices


def shorten_dict_values(obj: Union[List, Dict], max_length: int = 20) -> Union[List, Dict]:
    """Recursively shorten string values in dictionaries and lists. Useful for printing out data structures in a readable format.

    Args:
        obj: The data structure to shorten.
        max_length: The maximum length of string values to shorten.

    Returns:
        A new data structure with string values shortened.

    """
    if isinstance(obj, dict):
        return {k: shorten_dict_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [shorten_dict_values(item) for item in obj]
    elif isinstance(obj, str):
        return obj[:max_length] + "... (truncated)" if len(obj) > max_length else obj
    else:
        return obj
