"""Safety filtering for investor-facing interpretation conclusions."""

import re
from copy import deepcopy
from typing import Any, Mapping


_UNSUPPORTED_CONCLUSION_REPLACEMENTS = {
    "fraud": "possible misconduct that requires investigation",
    "manipulation": "a possible reporting concern that warrants review",
    "insolvency": "possible financial distress that requires investigation",
}


def _safe_text(value: str) -> str:
    result = value
    for unsupported, cautious in _UNSUPPORTED_CONCLUSION_REPLACEMENTS.items():
        result = re.sub(
            rf"\b{unsupported}\b",
            cautious,
            result,
            flags=re.IGNORECASE,
        )
    return result


def apply_conclusion_safety(value: Any) -> Any:
    """Return a safe copy without changing non-text evidence.

    Unsupported accusation terms are replaced with cautious investor-facing
    language. Dictionary keys, numeric evidence, booleans, flags, severity
    values, and missing values are preserved.
    """

    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, Mapping):
        return {
            deepcopy(key): apply_conclusion_safety(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [apply_conclusion_safety(item) for item in value]
    if isinstance(value, tuple):
        return tuple(apply_conclusion_safety(item) for item in value)
    return deepcopy(value)

