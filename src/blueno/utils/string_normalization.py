import re
from typing import Dict


def to_snake_case(text: str) -> str:
    r"""Convert a string to snake case.

    Args:
        text: The string to convert to snake case. Can be converted from PascalCase, camelCase, kebab-case, or mixed case. Non-alphanumeric characters are converted to underscores.

    Returns:
        The string in snake case.

    Example:
    ```python
    from blueno.utils import to_snake_case

    to_snake_case("CustomerID")
    "customer_id"
    ```
    """
    text = text.replace(" ", "_")
    text = text.replace("-", "_")
    text = re.sub(r"([a-z])([A-Z0-9])", r"\1_\2", text)
    text = re.sub(r"([A-Z0-9])([A-Z0-9][a-z])", r"\1_\2", text)
    text = re.sub(r"(?<!^)_{2,}", "_", text)
    return text.lower()


def character_translation(text: str, translation_map: Dict[str, str]) -> str:
    """Translate characters in a string using a translation map.

    Args:
        text: The string to translate.
        translation_map: A dictionary mapping characters to their replacements.

    Returns:
        The translated string.

    Example:
    ```python
    from blueno.utils import character_translation

    character_translation("Profit&Loss", {"&": "_and"})
    "Profit_and_Loss"
    ```
    """
    for character, replacement in translation_map.items():
        text = text.replace(character, replacement)
    return text
