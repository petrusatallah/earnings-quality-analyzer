"""Deterministic label mapping for the annual core financial metrics.

Mapping is based only on an explicit alias table.  Numeric values and XBRL
concepts are deliberately ignored, and no fuzzy matching is performed.
"""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Iterable, Mapping, Optional, Tuple

from Data.financial_statement_fetcher import FactStatus


STANDARD_ANNUAL_CORE_METRICS: Tuple[str, ...] = (
    "Revenue",
    "Net Income",
    "Operating Cash Flow",
    "Accounts Receivable",
    "Inventory",
    "Accounts Payable",
    "Depreciation & Amortization",
    "Capital Expenditures",
    "Stock-Based Compensation",
    "Shares Outstanding",
    "Income Tax Expense",
    "Deferred Tax Assets",
    "Deferred Tax Liabilities",
)

# Each alias must be accounting-equivalent to its target.  Broad concepts are
# kept out even when their wording resembles a core metric.
CONTROLLED_LABEL_ALIASES = {
    "Revenue": (
        "Revenue", "Revenues", "Sales Revenue",
    ),
    "Net Income": (
        "Net Income", "Net Earnings", "Net Income Loss",
    ),
    "Operating Cash Flow": (
        "Operating Cash Flow", "Cash Flow from Operations",
        "Cash Flows from Operations", "Net Cash Provided by Operating Activities",
        "Net Cash Provided by Used in Operating Activities",
    ),
    "Accounts Receivable": (
        "Accounts Receivable", "Receivables", "Trade Receivables",
        "Trade Accounts Receivable",
    ),
    "Inventory": ("Inventory", "Inventories"),
    "Accounts Payable": ("Accounts Payable", "Trade Payables"),
    "Depreciation & Amortization": (
        "Depreciation & Amortization", "Depreciation and Amortization", "D&A",
    ),
    "Capital Expenditures": (
        "Capital Expenditures", "Capital Expenditure", "CapEx", "Capital Spending",
    ),
    "Stock-Based Compensation": (
        "Stock-Based Compensation", "Stock Based Compensation",
        "Share-Based Compensation", "Share Based Compensation",
    ),
    "Shares Outstanding": (
        "Shares Outstanding", "Common Shares Outstanding",
        "Common Stock Shares Outstanding",
    ),
    "Income Tax Expense": (
        "Income Tax Expense", "Income Taxes Expense", "Tax Expense",
        "Provision for Income Taxes",
    ),
    "Deferred Tax Assets": ("Deferred Tax Assets", "Deferred Tax Asset"),
    "Deferred Tax Liabilities": (
        "Deferred Tax Liabilities", "Deferred Tax Liability",
    ),
}

# These labels are explicitly recognized as unsafe rather than merely unknown.
AMBIGUOUS_OR_BROADER_LABELS = (
    "Accounts Payable and Accrued Liabilities",
    "Current Liabilities",
    "Total Receivables",
    "Compensation Expense",
    "Investing Cash Flow",
    "Weighted Average Shares",
    "Weighted Average Shares Outstanding",
    "Weighted Average Number of Shares Outstanding",
    "Weighted Average Diluted Shares Outstanding",
)


class LabelMappingStatus(str, Enum):
    MAPPED = "MAPPED"
    UNMAPPED = "UNMAPPED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class LabelMappingResult:
    raw_label: Any
    standardized_metric: Optional[str]
    fiscal_year: Optional[int]
    mapping_status: LabelMappingStatus
    validation_status: FactStatus
    explanation: str
    mapping_rule: str
    original_record: Any = None

    @property
    def status(self) -> FactStatus:
        return self.validation_status


def _normalize_label(label: str) -> str:
    """Normalize harmless presentation differences, not accounting meaning."""

    text = label.strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[-‐‑–—]", " ", text)
    text = re.sub(r"[.,:;()]", " ", text)
    return " ".join(text.split())


_NORMALIZED_ALIASES = {
    _normalize_label(alias): metric
    for metric, aliases in CONTROLLED_LABEL_ALIASES.items()
    for alias in aliases
}
_NORMALIZED_AMBIGUOUS = frozenset(
    _normalize_label(label) for label in AMBIGUOUS_OR_BROADER_LABELS
)


def _attribute(record: Any, *names: str) -> Any:
    if isinstance(record, Mapping):
        for name in names:
            if name in record:
                return record[name]
    else:
        for name in names:
            if hasattr(record, name):
                return getattr(record, name)
    return None


def _status_text(status: Any) -> str:
    return str(getattr(status, "value", status) or "").strip().upper().replace("_", " ")


def map_annual_label(
    label_or_record: Any,
    *,
    extraction_status: Any = FactStatus.RETRIEVED,
) -> LabelMappingResult:
    """Map one raw annual metric label using only the controlled alias table."""

    if isinstance(label_or_record, str) or label_or_record is None:
        raw_label = label_or_record
        original_record = None
        underlying_status = extraction_status
        fiscal_year = None
    else:
        original_record = label_or_record
        raw_label = _attribute(
            label_or_record,
            "raw_label", "metric_name", "financial_field", "metric", "Metric",
        )
        underlying_status = _attribute(
            label_or_record, "status", "extraction_status", "Status"
        )
        raw_year = _attribute(label_or_record, "fiscal_year", "Fiscal Year")
        try:
            fiscal_year = int(raw_year) if raw_year is not None else None
        except (TypeError, ValueError):
            fiscal_year = None

    normalized = _normalize_label(raw_label) if isinstance(raw_label, str) else ""
    metric = _NORMALIZED_ALIASES.get(normalized)
    if metric is not None:
        mapping_status = LabelMappingStatus.MAPPED
        explanation = f"Raw label matched the controlled alias table for {metric}."
        rule = f"controlled_alias:{normalized}"
    elif normalized in _NORMALIZED_AMBIGUOUS:
        mapping_status = LabelMappingStatus.AMBIGUOUS
        explanation = (
            "The label is broader than, or materially different from, a core metric; "
            "it was not silently mapped."
        )
        rule = "explicit_ambiguous_or_broader_label"
    else:
        mapping_status = LabelMappingStatus.UNMAPPED
        explanation = "The label is unsupported by the controlled alias table; no guess was made."
        rule = "no_controlled_alias"

    status_text = _status_text(underlying_status)
    if status_text == FactStatus.MISSING.value:
        validation_status = FactStatus.MISSING
        explanation += " The underlying extraction remains MISSING."
    elif status_text != FactStatus.RETRIEVED.value:
        validation_status = FactStatus.NEEDS_VALIDATION
        explanation += " The underlying extraction was not upgraded."
    elif mapping_status is LabelMappingStatus.MAPPED:
        validation_status = FactStatus.RETRIEVED
    else:
        validation_status = FactStatus.NEEDS_VALIDATION

    return LabelMappingResult(
        raw_label=raw_label,
        standardized_metric=metric,
        fiscal_year=fiscal_year,
        mapping_status=mapping_status,
        validation_status=validation_status,
        explanation=explanation,
        mapping_rule=rule,
        original_record=original_record,
    )


map_label = map_annual_label


def map_annual_labels(records: Iterable[Any]) -> Tuple[LabelMappingResult, ...]:
    """Map labels for annual extraction records without modifying the records."""

    source_records = _attribute(records, "values")
    if source_records is None:
        source_records = records
    return tuple(map_annual_label(record) for record in source_records)


map_labels = map_annual_labels
