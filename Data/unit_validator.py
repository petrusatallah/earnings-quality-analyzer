"""Validate raw units on annual financial extraction records.

This module performs classification only.  It does not rewrite units, scale
values, normalize share counts, or perform foreign-exchange conversion.
"""

from dataclasses import dataclass
from enum import Enum
import math
from numbers import Real
from typing import Any, Iterable, Mapping, Optional, Tuple

from Data.financial_statement_fetcher import FactStatus


MONETARY_METRICS: Tuple[str, ...] = (
    "Revenue",
    "Net Income",
    "Operating Cash Flow",
    "Accounts Receivable",
    "Inventory",
    "Accounts Payable",
    "Depreciation & Amortization",
    "Capital Expenditures",
    "Stock-Based Compensation",
    "Income Tax Expense",
    "Deferred Tax Assets",
    "Deferred Tax Liabilities",
)
SHARE_COUNT_METRICS: Tuple[str, ...] = ("Shares Outstanding",)
REQUIRED_ANNUAL_CORE_METRICS = MONETARY_METRICS + SHARE_COUNT_METRICS

# Active ISO 4217 currency codes plus commonly encountered fund/metal codes.
# Extraction units are checked, never converted.  A bounded allow-list prevents
# arbitrary three-letter strings from being guessed to be currencies.
VALID_CURRENCY_UNITS = frozenset(
    "AED AFN ALL AMD AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB "
    "BOV BRL BSD BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC "
    "CUC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP "
    "GMD GNF GTQ GYD HKD HNL HRK HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY "
    "KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA "
    "MKD MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD "
    "OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD "
    "SHP SLE SLL SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS "
    "UAH UGX USD USN UYI UYU UYW UZS VED VES VND VUV WST XAF XAG XAU XBA XBB "
    "XBC XBD XCD XDR XOF XPD XPF XPT XSU XTS XUA XXX YER ZAR ZMW ZWL".split()
)
VALID_SHARE_UNITS = frozenset({"share", "shares"})

_METRIC_ALIASES = {
    "revenue": "Revenue",
    "net income": "Net Income",
    "operating cash flow": "Operating Cash Flow",
    "ocf": "Operating Cash Flow",
    "accounts receivable": "Accounts Receivable",
    "ar": "Accounts Receivable",
    "inventory": "Inventory",
    "accounts payable": "Accounts Payable",
    "ap": "Accounts Payable",
    "depreciation & amortization": "Depreciation & Amortization",
    "depreciation and amortization": "Depreciation & Amortization",
    "d&a": "Depreciation & Amortization",
    "capital expenditures": "Capital Expenditures",
    "capex": "Capital Expenditures",
    "stock-based compensation": "Stock-Based Compensation",
    "stock based compensation": "Stock-Based Compensation",
    "sbc": "Stock-Based Compensation",
    "shares outstanding": "Shares Outstanding",
    "income tax expense": "Income Tax Expense",
    "tax expense": "Income Tax Expense",
    "deferred tax assets": "Deferred Tax Assets",
    "dta": "Deferred Tax Assets",
    "deferred tax liabilities": "Deferred Tax Liabilities",
    "dtl": "Deferred Tax Liabilities",
}


class ExpectedUnitType(str, Enum):
    MONETARY = "MONETARY"
    SHARE_COUNT = "SHARE COUNT"


@dataclass(frozen=True)
class UnitValidationResult:
    metric: str
    fiscal_year: int
    raw_unit: Any
    expected_unit_type: ExpectedUnitType
    validation_status: FactStatus
    reason: Optional[str] = None
    unit_is_valid: Optional[bool] = None

    @property
    def status(self) -> FactStatus:
        """Compatibility alias for extraction records that expose ``status``."""

        return self.validation_status


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


def _canonical_metric(metric: Any) -> str:
    key = " ".join(str(metric).strip().lower().split())
    try:
        return _METRIC_ALIASES[key]
    except KeyError as error:
        raise ValueError(f"Unsupported annual core metric: {metric!r}") from error


def _status_text(status: Any) -> str:
    return str(getattr(status, "value", status) or "").strip().upper().replace("_", " ")


def _usable_numeric_value(record: Any) -> bool:
    value = _attribute(
        record, "raw_sec_value", "raw_value", "raw_amount", "value", "Value"
    )
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and (not isinstance(value, float) or math.isfinite(value))
    )


def validate_annual_unit(record: Any) -> UnitValidationResult:
    """Validate one annual extraction's raw unit without altering the record."""

    metric = _canonical_metric(
        _attribute(record, "metric_name", "financial_field", "metric", "Metric")
    )
    year = _attribute(record, "fiscal_year", "Fiscal Year")
    if year is None:
        raise ValueError("Annual unit validation requires a fiscal year")
    fiscal_year = int(year)
    raw_unit = _attribute(record, "raw_unit", "unit", "Raw Unit")
    expected = (
        ExpectedUnitType.SHARE_COUNT
        if metric in SHARE_COUNT_METRICS
        else ExpectedUnitType.MONETARY
    )
    extraction_status = _status_text(
        _attribute(record, "status", "extraction_status", "Status")
    )

    if not isinstance(raw_unit, str) or not raw_unit.strip():
        unit_is_valid = False
        unit_reason = "The raw unit is missing or blank; no unit was guessed."
    elif raw_unit != raw_unit.strip():
        unit_is_valid = False
        unit_reason = (
            "The raw unit is malformed; it was preserved and not silently rewritten."
        )
    elif expected is ExpectedUnitType.MONETARY:
        unit_is_valid = raw_unit in VALID_CURRENCY_UNITS
        unit_reason = None if unit_is_valid else (
            f"Raw unit {raw_unit!r} is not a recognized currency unit for a monetary metric."
        )
    else:
        unit_is_valid = raw_unit.lower() in VALID_SHARE_UNITS
        unit_reason = None if unit_is_valid else (
            f"Raw unit {raw_unit!r} is not a share-count unit for Shares Outstanding."
        )

    if extraction_status == FactStatus.MISSING.value:
        return UnitValidationResult(
            metric, fiscal_year, raw_unit, expected, FactStatus.MISSING,
            "The underlying annual extracted value is already MISSING.",
            unit_is_valid,
        )
    if extraction_status != FactStatus.RETRIEVED.value:
        return UnitValidationResult(
            metric, fiscal_year, raw_unit, expected, FactStatus.NEEDS_VALIDATION,
            "The underlying annual extraction is not in a usable RETRIEVED state.",
            unit_is_valid,
        )
    if not _usable_numeric_value(record):
        return UnitValidationResult(
            metric, fiscal_year, raw_unit, expected, FactStatus.NEEDS_VALIDATION,
            "The extracted value is not a usable numeric annual value.",
            unit_is_valid,
        )
    if not unit_is_valid:
        return UnitValidationResult(
            metric, fiscal_year, raw_unit, expected, FactStatus.NEEDS_VALIDATION,
            unit_reason,
            False,
        )

    return UnitValidationResult(
        metric=metric,
        fiscal_year=fiscal_year,
        raw_unit=raw_unit,
        expected_unit_type=expected,
        validation_status=FactStatus.RETRIEVED,
        reason=None,
        unit_is_valid=True,
    )


def validate_annual_units(records: Iterable[Any]) -> Tuple[UnitValidationResult, ...]:
    """Validate a collection of annual extraction records independently."""

    source_records = _attribute(records, "values")
    if source_records is None:
        source_records = records
    return tuple(validate_annual_unit(record) for record in source_records)


validate_unit = validate_annual_unit
validate_units = validate_annual_units
