"""Combine Tasks 91-96 into a final earnings-quality conclusion.

The final conclusion summarizes existing interpretation outputs only.  It does
not inspect financial data, calculate metrics, rank severity, or create a new
score.
"""

from copy import deepcopy
from typing import Any, Mapping, Optional

from Analysis.conclusion_safety import apply_conclusion_safety


_CATEGORIES = (
    ("accrual", "Accrual Quality"),
    ("working_capital", "Working Capital"),
    ("capex", "CapEx"),
    ("deferred_taxes", "Deferred Taxes"),
    ("sbc", "Stock-Based Compensation"),
    ("normalized_earnings", "Normalized Earnings"),
)
_WEAK_EXISTING_SEVERITIES = {"High", "Material Concern", "Weak"}


def _validate_interpretation(
    value: Optional[Mapping[str, Any]], category: str
) -> Optional[Mapping[str, Any]]:
    if value is not None and not isinstance(value, Mapping):
        raise TypeError(f"{category} interpretation must be a mapping or None.")
    return value


def _list_field(
    interpretation: Mapping[str, Any], *field_names: str
) -> list[Any]:
    for field_name in field_names:
        if field_name in interpretation:
            value = interpretation[field_name]
            if value is None:
                return []
            if not isinstance(value, list):
                raise TypeError(
                    f"Interpretation field {field_name!r} must be a list."
                )
            return value
    return []


def _contains_weak_existing_severity(value: Any) -> bool:
    """Inspect supplied severity labels without scoring or remapping them."""

    if isinstance(value, Mapping):
        return any(
            _contains_weak_existing_severity(item) for item in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_weak_existing_severity(item) for item in value)
    return value in _WEAK_EXISTING_SEVERITIES


def build_final_earnings_quality_conclusion(
    *,
    accrual: Optional[Mapping[str, Any]],
    working_capital: Optional[Mapping[str, Any]],
    capex: Optional[Mapping[str, Any]],
    deferred_taxes: Optional[Mapping[str, Any]],
    sbc: Optional[Mapping[str, Any]],
    normalized_earnings: Optional[Mapping[str, Any]],
    existing_overall_severity: Any,
) -> dict[str, Any]:
    """Summarize the six existing interpretations without new analysis rules."""

    supplied = {
        "accrual": accrual,
        "working_capital": working_capital,
        "capex": capex,
        "deferred_taxes": deferred_taxes,
        "sbc": sbc,
        "normalized_earnings": normalized_earnings,
    }

    supporting_by_category = {}
    positive_signals = []
    concerns = []
    investigation_areas = []
    category_severities = {}
    fiscal_years = []
    unavailable_areas = []

    for key, area_name in _CATEGORIES:
        interpretation = _validate_interpretation(supplied[key], key)
        if interpretation is None:
            unavailable_areas.append(area_name)
            category_severities[key] = None
            supporting_by_category[key] = {
                "area": area_name,
                "availability": "unavailable",
                "interpretation": None,
                "explanation": (
                    f"{area_name} interpretation was not supplied and was not invented."
                ),
            }
            continue

        preserved = deepcopy(dict(interpretation))
        supporting_by_category[key] = {
            "area": area_name,
            "availability": "available",
            "interpretation": preserved,
        }
        category_severities[key] = deepcopy(
            interpretation.get("existing_severities")
        )

        for fiscal_year in _list_field(
            interpretation, "fiscal_years_discussed"
        ):
            if fiscal_year not in fiscal_years:
                fiscal_years.append(deepcopy(fiscal_year))

        area_positives = _list_field(
            interpretation, "key_positive_signals", "positive_signals"
        )
        area_concerns = _list_field(
            interpretation, "key_concerns", "concerns"
        )
        positive_signals.extend(
            {"area": area_name, "signal": deepcopy(signal)}
            for signal in area_positives
        )
        concerns.extend(
            {"area": area_name, "concern": deepcopy(concern)}
            for concern in area_concerns
        )
        if area_concerns:
            investigation_areas.append(
                {
                    "area": area_name,
                    "existing_severities": deepcopy(
                        interpretation.get("existing_severities")
                    ),
                    "concerns": deepcopy(area_concerns),
                }
            )

    has_weak_existing_severity = any(
        _contains_weak_existing_severity(value)
        for value in category_severities.values()
        if value is not None
    )
    all_areas_have_positive_signals = all(
        supporting_by_category[key]["availability"] == "available"
        and bool(
            _list_field(
                supporting_by_category[key]["interpretation"],
                "key_positive_signals",
                "positive_signals",
            )
        )
        for key, _ in _CATEGORIES
    )

    if has_weak_existing_severity and concerns:
        conclusion = "Weak"
        explanation = (
            "At least one supplied interpretation combines an existing severe "
            "severity label with a stated concern. The underlying category "
            "severity and concern are preserved without creating a new score."
        )
    elif concerns or unavailable_areas:
        conclusion = "Needs Investigation"
        explanation = (
            "One or more supplied interpretations identify concerns or are "
            "unavailable, so further investigation is needed. Existing flags, "
            "conclusions, and severities remain unchanged."
        )
    elif all_areas_have_positive_signals:
        conclusion = "Strong"
        explanation = (
            "All six supplied interpretation areas are available, each reports a "
            "positive signal, and none reports a concern. No new financial test or "
            "severity score was created."
        )
    else:
        conclusion = "Generally Healthy"
        explanation = (
            "All six supplied interpretation areas are available and none reports "
            "a concern, although positive signals are not present in every area. "
            "No new financial test or severity score was created."
        )

    if unavailable_areas:
        explanation += (
            " Unavailable areas were not filled with invented evidence: "
            + ", ".join(unavailable_areas)
            + "."
        )

    result = apply_conclusion_safety({
        "earnings_quality_conclusion": conclusion,
        "explanation": explanation,
        "positive_signals": positive_signals,
        "key_concerns": concerns,
        "areas_needing_investigation": investigation_areas,
        "fiscal_years_covered": fiscal_years,
        "supporting_interpretation_by_category": supporting_by_category,
    })
    # Task 90's existing overall-severity object is authoritative and must be
    # returned byte-for-byte in meaning, not sanitized, remapped, or rebuilt.
    result["existing_overall_severity"] = deepcopy(existing_overall_severity)
    return result
