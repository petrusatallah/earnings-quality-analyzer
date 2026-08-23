"""Retrieve annual financial statement facts from official SEC EDGAR APIs.

This module is a retrieval layer only. It preserves values exactly as reported
by the SEC, performs no financial analysis, and does not alter benchmark data.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum
import json
import re
import time
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from Data.company_identifier import (
    CompanyIdentity,
    IdentificationStatus,
    identify_company,
    normalize_ticker_input,
)
from Data.source_policy import SourceClassification, classify_source
from Data.provenance import ProvenanceMixin


SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
ANNUAL_FORMS = ("10-K", "20-F", "40-F")
FULL_YEAR_MIN_DAYS = 330
FULL_YEAR_MAX_DAYS = 400


class FinancialStatementFetchError(RuntimeError):
    """Base error for SEC retrieval failures."""


class InvalidUserAgentError(FinancialStatementFetchError):
    """Raised when an identifying SEC User-Agent was not supplied."""


class CompanyNotFoundError(FinancialStatementFetchError):
    """Raised when an input cannot be mapped to one SEC CIK."""


class AmbiguousCompanyError(FinancialStatementFetchError):
    """Raised instead of guessing between multiple SEC companies."""


class SecRequestError(FinancialStatementFetchError):
    """Raised when an official SEC endpoint cannot be read."""


class TransientSecRequestError(SecRequestError):
    """A retryable SEC response such as HTTP 429 or a server error."""

    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class FactStatus(str, Enum):
    RETRIEVED = "RETRIEVED"
    MISSING = "MISSING"
    NEEDS_VALIDATION = "NEEDS VALIDATION"


@dataclass(frozen=True)
class ConceptCandidate:
    """One possible taxonomy/concept for a financial field, in priority order."""

    taxonomy: str
    concept: str


@dataclass(frozen=True)
class FinancialFieldDefinition:
    name: str
    statement: str
    duration: bool
    concepts: Tuple[ConceptCandidate, ...]


def _concepts(taxonomy: str, *names: str) -> Tuple[ConceptCandidate, ...]:
    return tuple(ConceptCandidate(taxonomy, name) for name in names)


# Candidate order is intentional. No fallback value is derived or combined:
# the first valid company-filed concept for a fiscal year is retained raw.
FINANCIAL_FIELD_DEFINITIONS: Tuple[FinancialFieldDefinition, ...] = (
    FinancialFieldDefinition(
        "Revenue", "Income Statement", True,
        _concepts(
            "us-gaap",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
            "SalesRevenueGoodsNet",
        ) + _concepts("ifrs-full", "Revenue"),
    ),
    FinancialFieldDefinition(
        "Net Income", "Income Statement", True,
        _concepts("us-gaap", "NetIncomeLoss", "ProfitLoss")
        + _concepts("ifrs-full", "ProfitLoss"),
    ),
    FinancialFieldDefinition(
        "Operating Cash Flow", "Cash Flow Statement", True,
        _concepts(
            "us-gaap",
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ) + _concepts("ifrs-full", "CashFlowsFromUsedInOperatingActivities"),
    ),
    FinancialFieldDefinition(
        "Accounts Receivable", "Balance Sheet", False,
        _concepts(
            "us-gaap",
            "AccountsReceivableNetCurrent",
            "AccountsNotesAndLoansReceivableNetCurrent",
            "AccountsReceivableNet",
        ) + _concepts("ifrs-full", "TradeAndOtherCurrentReceivables"),
    ),
    FinancialFieldDefinition(
        "Inventory", "Balance Sheet", False,
        _concepts("us-gaap", "InventoryNet", "InventoryNetOfAllowancesCustomerAdvancesAndProgressBillings")
        + _concepts("ifrs-full", "Inventories"),
    ),
    FinancialFieldDefinition(
        "Accounts Payable", "Balance Sheet", False,
        _concepts("us-gaap", "AccountsPayableCurrent")
        + _concepts("ifrs-full", "TradePayablesCurrent", "TradePayables"),
    ),
    FinancialFieldDefinition(
        "Depreciation & Amortization", "Cash Flow Statement", True,
        _concepts(
            "us-gaap",
            "DepreciationDepletionAndAmortization",
            "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
        ) + _concepts("ifrs-full", "DepreciationAndAmortisationExpense"),
    ),
    FinancialFieldDefinition(
        "Capital Expenditures", "Cash Flow Statement", True,
        _concepts(
            "us-gaap",
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsForAdditionsToPropertyPlantAndEquipment",
            "PaymentsToAcquireProductiveAssets",
        ) + _concepts(
            "ifrs-full", "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"
        ),
    ),
    FinancialFieldDefinition(
        "Stock-Based Compensation", "Cash Flow Statement", True,
        _concepts(
            "us-gaap",
            "ShareBasedCompensation",
            "AllocatedShareBasedCompensationExpense",
        ) + _concepts("ifrs-full", "ShareBasedPayment"),
    ),
    FinancialFieldDefinition(
        "Shares Outstanding", "Balance Sheet", False,
        _concepts(
            "us-gaap",
            "CommonStockSharesOutstanding",
        )
        + _concepts("dei", "EntityCommonStockSharesOutstanding")
        + _concepts("ifrs-full", "NumberOfSharesOutstanding"),
    ),
    FinancialFieldDefinition(
        "Income Tax Expense", "Income Statement", True,
        _concepts("us-gaap", "IncomeTaxExpenseBenefit")
        + _concepts("ifrs-full", "IncomeTaxExpenseContinuingOperations", "IncomeTaxExpenseBenefit"),
    ),
    FinancialFieldDefinition(
        "Deferred Tax Assets", "Balance Sheet", False,
        _concepts(
            "us-gaap",
            "DeferredTaxAssetsNet",
            "DeferredTaxAssetsGross",
            "DeferredTaxAssetsNetCurrent",
            "DeferredTaxAssetsNetNoncurrent",
        ) + _concepts("ifrs-full", "DeferredTaxAssets"),
    ),
    FinancialFieldDefinition(
        "Deferred Tax Liabilities", "Balance Sheet", False,
        _concepts(
            "us-gaap",
            "DeferredIncomeTaxLiabilities",
            "DeferredTaxLiabilities",
            "DeferredTaxLiabilitiesCurrent",
            "DeferredTaxLiabilitiesNoncurrent",
        ) + _concepts("ifrs-full", "DeferredTaxLiabilities"),
    ),
)


# These concepts are useful evidence, but they do not report the combined D&A
# metric and therefore must never populate its selected value.
DEPRECIATION_ONLY_DA_CONCEPTS = _concepts("us-gaap", "Depreciation")


@dataclass(frozen=True)
class SecCompany:
    company_name: str
    ticker: str
    cik: str


@dataclass(frozen=True)
class CandidateFinancialValue:
    """An unselected SEC candidate retained for human validation."""

    raw_value: Any
    unit: str
    filing_form: Optional[str]
    filing_date: Optional[str]
    accession_number: Optional[str]
    source_url: str
    xbrl_taxonomy: str
    xbrl_concept: str
    period_start: Optional[str]
    period_end: Optional[str]


@dataclass(frozen=True)
class AnnualFinancialValue(ProvenanceMixin):
    """One selected raw SEC fact, explicit missing marker, or candidate set."""

    financial_field: str
    financial_statement: str
    fiscal_year: int
    status: FactStatus
    raw_value: Any = None
    filing_form: Optional[str] = None
    filing_date: Optional[str] = None
    accession_number: Optional[str] = None
    source_url: Optional[str] = None
    sec_source_identifier: Optional[str] = None
    xbrl_taxonomy: Optional[str] = None
    xbrl_concept: Optional[str] = None
    unit: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    missing_reason: Optional[str] = None
    validation_reason: Optional[str] = None
    candidate_values: Tuple[CandidateFinancialValue, ...] = ()

    @property
    def is_missing(self) -> bool:
        return self.status is FactStatus.MISSING

    @property
    def needs_validation(self) -> bool:
        return self.status is FactStatus.NEEDS_VALIDATION


@dataclass(frozen=True)
class AnnualFinancialStatements:
    company_name: str
    ticker: str
    cik: str
    source_classification: SourceClassification
    values: Tuple[AnnualFinancialValue, ...]
    company_facts_url: str
    warnings: Tuple[str, ...] = ()

    def for_fiscal_year(self, fiscal_year: int) -> Tuple[AnnualFinancialValue, ...]:
        return tuple(value for value in self.values if value.fiscal_year == fiscal_year)


JsonLoader = Callable[[str, Mapping[str, str], float], Mapping[str, Any]]
TextLoader = Callable[[str, Mapping[str, str], float], str]


def _default_json_loader(
    url: str, headers: Mapping[str, str], timeout: float
) -> Mapping[str, Any]:
    request = Request(url, headers=dict(headers), method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 429 or 500 <= error.code <= 599:
            retry_after = None
            if error.headers:
                try:
                    retry_after = float(error.headers.get("Retry-After", ""))
                except (TypeError, ValueError):
                    pass
            raise TransientSecRequestError(
                f"Temporary SEC HTTP {error.code} response from {url}", retry_after
            ) from error
        raise SecRequestError(
            f"Unable to retrieve official SEC data from {url}: {error}"
        ) from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise SecRequestError(f"Unable to retrieve official SEC data from {url}: {error}") from error


def _default_text_loader(
    url: str, headers: Mapping[str, str], timeout: float
) -> str:
    request = Request(url, headers=dict(headers), method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        if error.code == 429 or 500 <= error.code <= 599:
            retry_after = None
            if error.headers:
                try:
                    retry_after = float(error.headers.get("Retry-After", ""))
                except (TypeError, ValueError):
                    pass
            raise TransientSecRequestError(
                f"Temporary SEC HTTP {error.code} response from {url}", retry_after
            ) from error
        raise SecRequestError(
            f"Unable to retrieve official SEC document from {url}: {error}"
        ) from error
    except (URLError, TimeoutError) as error:
        raise SecRequestError(
            f"Unable to retrieve official SEC document from {url}: {error}"
        ) from error


class SECFinancialStatementFetcher:
    """CIK resolver and annual Company Facts retriever for SEC registrants."""

    def __init__(
        self,
        user_agent: str,
        *,
        timeout: float = 30.0,
        minimum_request_interval: float = 0.11,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
        json_loader: Optional[JsonLoader] = None,
        text_loader: Optional[TextLoader] = None,
    ) -> None:
        if not isinstance(user_agent, str) or not re.search(
            r"\S+\s+\S+@\S+\.\S+", user_agent.strip()
        ):
            raise InvalidUserAgentError(
                "Use an identifying User-Agent such as "
                "'EarningsQualityAgent contact@example.com'."
            )
        if (
            timeout <= 0
            or minimum_request_interval < 0
            or max_retries < 0
            or retry_backoff_seconds < 0
        ):
            raise ValueError("SEC timing and retry settings cannot be negative")

        self.user_agent = user_agent.strip()
        self.timeout = timeout
        self.minimum_request_interval = max(minimum_request_interval, 0.11)
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._json_loader = json_loader or _default_json_loader
        self._text_loader = text_loader or _default_text_loader
        self._last_request_at: Optional[float] = None
        self._ticker_payload: Optional[Mapping[str, Any]] = None
        self._response_cache: dict[str, Mapping[str, Any]] = {}
        self._text_response_cache: dict[str, str] = {}

    @property
    def headers(self) -> Mapping[str, str]:
        return {"User-Agent": self.user_agent, "Accept": "application/json"}

    def _get_json(self, url: str) -> Mapping[str, Any]:
        if classify_source(url) is not SourceClassification.PRIMARY:
            raise SecRequestError(f"Refusing non-primary source URL: {url}")

        if url in self._response_cache:
            return self._response_cache[url]

        payload = None
        for attempt in range(self.max_retries + 1):
            if self._last_request_at is not None:
                remaining = self.minimum_request_interval - (
                    time.monotonic() - self._last_request_at
                )
                if remaining > 0:
                    time.sleep(remaining)
            try:
                payload = self._json_loader(url, self.headers, self.timeout)
                break
            except TransientSecRequestError as error:
                if attempt >= self.max_retries:
                    raise
                backoff = self.retry_backoff_seconds * (2**attempt)
                time.sleep(max(backoff, error.retry_after or 0.0))
            finally:
                self._last_request_at = time.monotonic()
        if not isinstance(payload, Mapping):
            raise SecRequestError(f"SEC endpoint returned an invalid JSON object: {url}")
        self._response_cache[url] = payload
        return payload

    def _ticker_records(self) -> Tuple[SecCompany, ...]:
        if self._ticker_payload is None:
            self._ticker_payload = self._get_json(SEC_TICKER_URL)

        records = []
        for item in self._ticker_payload.values():
            if not isinstance(item, Mapping):
                continue
            ticker = normalize_ticker_input(str(item.get("ticker", "")))
            title = str(item.get("title", "")).strip()
            try:
                cik = f"{int(item['cik_str']):010d}"
            except (KeyError, TypeError, ValueError):
                continue
            if ticker and title:
                records.append(SecCompany(title, ticker, cik))
        return tuple(records)

    def list_companies(self) -> Tuple[SecCompany, ...]:
        """Return the official SEC company/ticker universe."""

        return self._ticker_records()

    def get_official_json(self, url: str) -> Mapping[str, Any]:
        """Read cached JSON from an approved primary SEC endpoint."""

        return self._get_json(url)

    def get_official_filing_text(self, url: str) -> str:
        """Read and cache an official SEC filing through the existing client."""

        if classify_source(url) is not SourceClassification.PRIMARY:
            raise SecRequestError(f"Refusing non-primary filing URL: {url}")
        if url in self._text_response_cache:
            return self._text_response_cache[url]

        document = None
        for attempt in range(self.max_retries + 1):
            if self._last_request_at is not None:
                remaining = self.minimum_request_interval - (
                    time.monotonic() - self._last_request_at
                )
                if remaining > 0:
                    time.sleep(remaining)
            try:
                document = self._text_loader(url, self.headers, self.timeout)
                break
            except TransientSecRequestError as error:
                if attempt >= self.max_retries:
                    raise
                backoff = self.retry_backoff_seconds * (2**attempt)
                time.sleep(max(backoff, error.retry_after or 0.0))
            finally:
                self._last_request_at = time.monotonic()
        if not isinstance(document, str) or not document.strip():
            raise SecRequestError(f"SEC filing returned no readable text: {url}")
        self._text_response_cache[url] = document
        return document

    def resolve_cik(self, company: Union[CompanyIdentity, str]) -> SecCompany:
        """Resolve exactly one official SEC ticker record without guessing."""

        if isinstance(company, CompanyIdentity):
            ticker = normalize_ticker_input(company.ticker)
        elif isinstance(company, str):
            local_result = identify_company(company)
            if local_result.status is IdentificationStatus.AMBIGUOUS:
                raise AmbiguousCompanyError(local_result.message)
            ticker = (
                normalize_ticker_input(local_result.company.ticker)
                if local_result.matched and local_result.company
                else normalize_ticker_input(company)
            )
        else:
            raise TypeError("company must be a CompanyIdentity or ticker string")

        if not ticker:
            raise CompanyNotFoundError(
                "A standardized company identity or valid ticker is required."
            )

        matches = tuple(record for record in self._ticker_records() if record.ticker == ticker)
        if len(matches) > 1:
            raise AmbiguousCompanyError(
                f"Ticker {ticker!r} maps to multiple SEC registrants; no CIK was selected."
            )
        if not matches:
            raise CompanyNotFoundError(
                f"Ticker {ticker!r} was not found in the official SEC ticker mapping."
            )
        return matches[0]

    def fetch(
        self,
        company: Union[CompanyIdentity, str],
        *,
        fiscal_years: Optional[Iterable[int]] = None,
    ) -> AnnualFinancialStatements:
        """Retrieve raw annual facts and explicit missing values from the SEC."""

        sec_company = self.resolve_cik(company)
        facts_url = SEC_COMPANY_FACTS_URL.format(cik=sec_company.cik)
        payload = self._get_json(facts_url)
        available_years = _discover_annual_years(payload)

        if fiscal_years is None:
            selected_years = available_years
        else:
            requested = tuple(sorted({int(year) for year in fiscal_years}))
            selected_years = requested

        values = tuple(
            _extract_field(payload, definition, year, sec_company.cik, facts_url)
            for year in selected_years
            for definition in FINANCIAL_FIELD_DEFINITIONS
        )
        return AnnualFinancialStatements(
            company_name=sec_company.company_name,
            ticker=sec_company.ticker,
            cik=sec_company.cik,
            source_classification=classify_source(facts_url),
            values=values,
            company_facts_url=facts_url,
            warnings=(
                ()
                if selected_years
                else (
                    "No annual 10-K, 20-F, or 40-F fiscal years were found; "
                    "no values were guessed.",
                )
            ),
        )


def _valid_iso_date(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def _annual_form_base(form: Any) -> Optional[str]:
    if not isinstance(form, str):
        return None
    base_form = form[:-2] if form.endswith("/A") else form
    return base_form if base_form in ANNUAL_FORMS else None


def _is_annual_entry(entry: Mapping[str, Any], *, duration: Optional[bool] = None) -> bool:
    if _annual_form_base(entry.get("form")) is None or entry.get("fp") != "FY":
        return False
    if not isinstance(entry.get("fy"), int):
        return False
    end = _valid_iso_date(entry.get("end"))
    if end is None:
        return False
    if duration is True:
        start = _valid_iso_date(entry.get("start"))
        if start is None:
            return False
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days
        return FULL_YEAR_MIN_DAYS <= days <= FULL_YEAR_MAX_DAYS
    if duration is False and entry.get("start") is not None:
        return False
    return True


def _iter_fact_units(payload: Mapping[str, Any]) -> Iterable[Tuple[str, str, str, Mapping[str, Any]]]:
    facts = payload.get("facts", {})
    if not isinstance(facts, Mapping):
        return
    for taxonomy, taxonomy_facts in facts.items():
        if not isinstance(taxonomy_facts, Mapping):
            continue
        for concept, concept_payload in taxonomy_facts.items():
            if not isinstance(concept_payload, Mapping):
                continue
            units = concept_payload.get("units", {})
            if not isinstance(units, Mapping):
                continue
            for unit, entries in units.items():
                if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
                    continue
                for entry in entries:
                    if isinstance(entry, Mapping):
                        yield str(taxonomy), str(concept), str(unit), entry


def _discover_annual_years(payload: Mapping[str, Any]) -> Tuple[int, ...]:
    years = {
        int(entry["fy"])
        for _, _, _, entry in _iter_fact_units(payload)
        if _is_annual_entry(entry)
    }
    return tuple(sorted(years))


def _entry_sort_key(item: Tuple[str, Mapping[str, Any]]) -> Tuple[str, str, int]:
    unit, entry = item
    base_form = _annual_form_base(entry.get("form"))
    form_rank = len(ANNUAL_FORMS) - ANNUAL_FORMS.index(str(base_form))
    amendment_rank = 1 if str(entry.get("form", "")).endswith("/A") else 0
    return str(entry.get("end", "")), str(entry.get("filed", "")), form_rank + amendment_rank


def _candidate_value(
    candidate: ConceptCandidate,
    unit: str,
    entry: Mapping[str, Any],
    cik: str,
    facts_url: str,
) -> CandidateFinancialValue:
    accession = str(entry.get("accn", "")) or None
    accession_path = accession.replace("-", "") if accession else None
    source_url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/"
        if accession_path
        else facts_url
    )
    return CandidateFinancialValue(
        raw_value=entry.get("val"),
        unit=unit,
        filing_form=str(entry.get("form")) if entry.get("form") else None,
        filing_date=str(entry.get("filed")) if entry.get("filed") else None,
        accession_number=accession,
        source_url=source_url,
        xbrl_taxonomy=candidate.taxonomy,
        xbrl_concept=candidate.concept,
        period_start=str(entry.get("start")) if entry.get("start") else None,
        period_end=str(entry.get("end")) if entry.get("end") else None,
    )


def _annual_fiscal_year_end(
    payload: Mapping[str, Any], fiscal_year: int
) -> Optional[str]:
    """Return the end of the requested fiscal year's full-year annual period."""

    period_ends = (
        str(entry["end"])
        for _, _, _, entry in _iter_fact_units(payload)
        if entry.get("fy") == fiscal_year
        and entry.get("val") is not None
        and _is_annual_entry(entry, duration=True)
    )
    return max(period_ends, default=None)


def _shares_annual_preference(
    entry: Mapping[str, Any], fiscal_year: int
) -> Tuple[int, int, int]:
    """Rank annual share facts without using a different period as a fallback."""

    base_form = _annual_form_base(entry.get("form"))
    form_rank = (
        len(ANNUAL_FORMS) - ANNUAL_FORMS.index(str(base_form))
        if base_form in ANNUAL_FORMS
        else 0
    )
    return (
        form_rank,
        1 if entry.get("fy") == fiscal_year else 0,
        1 if entry.get("fp") == "FY" else 0,
    )


def _extract_shares_outstanding(
    payload: Mapping[str, Any],
    definition: FinancialFieldDefinition,
    fiscal_year: int,
    cik: str,
    facts_url: str,
) -> AnnualFinancialValue:
    """Select an explicitly reported fiscal-year-end annual share-count fact."""

    fiscal_year_end = _annual_fiscal_year_end(payload, fiscal_year)
    facts = payload.get("facts", {})
    if fiscal_year_end is not None and isinstance(facts, Mapping):
        for candidate in definition.concepts:
            taxonomy_facts = facts.get(candidate.taxonomy, {})
            concept_payload = (
                taxonomy_facts.get(candidate.concept, {})
                if isinstance(taxonomy_facts, Mapping)
                else {}
            )
            units = (
                concept_payload.get("units", {})
                if isinstance(concept_payload, Mapping)
                else {}
            )
            matches = []
            if isinstance(units, Mapping):
                for unit, entries in units.items():
                    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
                        continue
                    matches.extend(
                        (str(unit), entry)
                        for entry in entries
                        if isinstance(entry, Mapping)
                        and entry.get("val") is not None
                        and entry.get("start") is None
                        and _annual_form_base(entry.get("form")) is not None
                        and _valid_iso_date(entry.get("end")) == fiscal_year_end
                    )
            if not matches:
                continue

            preferred_rank = max(
                _shares_annual_preference(entry, fiscal_year)
                for _, entry in matches
            )
            preferred_matches = tuple(
                match
                for match in matches
                if _shares_annual_preference(match[1], fiscal_year) == preferred_rank
            )
            distinct_values = {
                (unit, repr(entry.get("val")))
                for unit, entry in preferred_matches
            }
            if len(distinct_values) > 1:
                return AnnualFinancialValue(
                    financial_field=definition.name,
                    financial_statement=definition.statement,
                    fiscal_year=fiscal_year,
                    status=FactStatus.NEEDS_VALIDATION,
                    source_url=facts_url,
                    sec_source_identifier=f"CIK{cik}:companyfacts",
                    xbrl_taxonomy=candidate.taxonomy,
                    xbrl_concept=candidate.concept,
                    validation_reason=(
                        "Conflicting original or amended annual SEC facts exist for "
                        "the fiscal-year-end Shares Outstanding concept; no value "
                        "was selected."
                    ),
                    candidate_values=tuple(
                        _candidate_value(candidate, unit, entry, cik, facts_url)
                        for unit, entry in preferred_matches
                    ),
                )

            unit, entry = max(preferred_matches, key=_entry_sort_key)
            accession = str(entry.get("accn", "")) or None
            accession_path = accession.replace("-", "") if accession else None
            source_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/"
                if accession_path
                else facts_url
            )
            if classify_source(source_url) is not SourceClassification.PRIMARY:
                raise SecRequestError(
                    f"SEC fact produced a non-primary source URL: {source_url}"
                )
            return AnnualFinancialValue(
                financial_field=definition.name,
                financial_statement=definition.statement,
                fiscal_year=fiscal_year,
                status=FactStatus.RETRIEVED,
                raw_value=entry["val"],
                filing_form=str(entry.get("form")) if entry.get("form") else None,
                filing_date=str(entry.get("filed")) if entry.get("filed") else None,
                accession_number=accession,
                source_url=source_url,
                sec_source_identifier=f"CIK{cik}:{accession or 'companyfacts'}",
                xbrl_taxonomy=candidate.taxonomy,
                xbrl_concept=candidate.concept,
                unit=unit,
                period_start=None,
                period_end=fiscal_year_end,
            )

    return AnnualFinancialValue(
        financial_field=definition.name,
        financial_statement=definition.statement,
        fiscal_year=fiscal_year,
        status=FactStatus.MISSING,
        source_url=facts_url,
        sec_source_identifier=f"CIK{cik}:companyfacts",
        missing_reason=(
            "No valid fiscal-year-end annual 10-K, 20-F, or 40-F Shares "
            "Outstanding fact was found for any approved point-in-time XBRL "
            "concept; no value was guessed."
        ),
    )


def _extract_field(
    payload: Mapping[str, Any],
    definition: FinancialFieldDefinition,
    fiscal_year: int,
    cik: str,
    facts_url: str,
) -> AnnualFinancialValue:
    if definition.name == "Shares Outstanding":
        return _extract_shares_outstanding(
            payload, definition, fiscal_year, cik, facts_url
        )

    facts = payload.get("facts", {})
    unreliable_annual_candidates = []
    for candidate in definition.concepts:
        taxonomy_facts = facts.get(candidate.taxonomy, {}) if isinstance(facts, Mapping) else {}
        concept_payload = (
            taxonomy_facts.get(candidate.concept, {})
            if isinstance(taxonomy_facts, Mapping)
            else {}
        )
        units = concept_payload.get("units", {}) if isinstance(concept_payload, Mapping) else {}
        matches = []
        if isinstance(units, Mapping):
            for unit, entries in units.items():
                if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
                    continue
                matches.extend(
                    (str(unit), entry)
                    for entry in entries
                    if isinstance(entry, Mapping)
                    and entry.get("fy") == fiscal_year
                    and _is_annual_entry(entry, duration=definition.duration)
                    and entry.get("val") is not None
                )
                unreliable_annual_candidates.extend(
                    (candidate, str(unit), entry)
                    for entry in entries
                    if isinstance(entry, Mapping)
                    and entry.get("fy") == fiscal_year
                    and _annual_form_base(entry.get("form")) is not None
                    and entry.get("val") is not None
                    and not _is_annual_entry(entry, duration=definition.duration)
                )
        if not matches:
            continue

        latest_period_end = max(str(entry.get("end", "")) for _, entry in matches)
        latest_period_matches = tuple(
            match for match in matches if str(match[1].get("end", "")) == latest_period_end
        )
        distinct_period_values = {
            (unit, repr(entry.get("val")))
            for unit, entry in latest_period_matches
        }
        if len(distinct_period_values) > 1:
            return AnnualFinancialValue(
                financial_field=definition.name,
                financial_statement=definition.statement,
                fiscal_year=fiscal_year,
                status=FactStatus.NEEDS_VALIDATION,
                source_url=facts_url,
                sec_source_identifier=f"CIK{cik}:companyfacts",
                xbrl_taxonomy=candidate.taxonomy,
                xbrl_concept=candidate.concept,
                validation_reason=(
                    "Conflicting original or amended annual SEC facts exist for "
                    "the selected XBRL concept and period; no value was selected."
                ),
                candidate_values=tuple(
                    _candidate_value(candidate, unit, entry, cik, facts_url)
                    for unit, entry in latest_period_matches
                ),
            )

        unit, entry = max(latest_period_matches, key=_entry_sort_key)
        accession = str(entry.get("accn", "")) or None
        accession_path = accession.replace("-", "") if accession else None
        source_url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/"
            if accession_path
            else facts_url
        )
        if classify_source(source_url) is not SourceClassification.PRIMARY:
            raise SecRequestError(f"SEC fact produced a non-primary source URL: {source_url}")

        return AnnualFinancialValue(
            financial_field=definition.name,
            financial_statement=definition.statement,
            fiscal_year=fiscal_year,
            status=FactStatus.RETRIEVED,
            raw_value=entry["val"],
            filing_form=str(entry.get("form")) if entry.get("form") else None,
            filing_date=str(entry.get("filed")) if entry.get("filed") else None,
            accession_number=accession,
            source_url=source_url,
            sec_source_identifier=f"CIK{cik}:{accession or 'companyfacts'}",
            xbrl_taxonomy=candidate.taxonomy,
            xbrl_concept=candidate.concept,
            unit=unit,
            period_start=str(entry.get("start")) if entry.get("start") else None,
            period_end=str(entry.get("end")) if entry.get("end") else None,
        )

    if unreliable_annual_candidates:
        candidate, unit, entry = unreliable_annual_candidates[0]
        return AnnualFinancialValue(
            financial_field=definition.name,
            financial_statement=definition.statement,
            fiscal_year=fiscal_year,
            status=FactStatus.NEEDS_VALIDATION,
            source_url=facts_url,
            sec_source_identifier=f"CIK{cik}:companyfacts",
            xbrl_taxonomy=candidate.taxonomy,
            xbrl_concept=candidate.concept,
            unit=unit,
            validation_reason=(
                "One or more candidate SEC facts exist, but they do not satisfy "
                "the annual-period reliability rules; no value was selected."
            ),
            candidate_values=tuple(
                _candidate_value(item_candidate, item_unit, item_entry, cik, facts_url)
                for item_candidate, item_unit, item_entry in unreliable_annual_candidates
            ),
        )

    if definition.name == "Depreciation & Amortization":
        depreciation_only_candidates = []
        for candidate in DEPRECIATION_ONLY_DA_CONCEPTS:
            taxonomy_facts = (
                facts.get(candidate.taxonomy, {})
                if isinstance(facts, Mapping)
                else {}
            )
            concept_payload = (
                taxonomy_facts.get(candidate.concept, {})
                if isinstance(taxonomy_facts, Mapping)
                else {}
            )
            units = (
                concept_payload.get("units", {})
                if isinstance(concept_payload, Mapping)
                else {}
            )
            if not isinstance(units, Mapping):
                continue
            for unit, entries in units.items():
                if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
                    continue
                depreciation_only_candidates.extend(
                    (candidate, str(unit), entry)
                    for entry in entries
                    if isinstance(entry, Mapping)
                    and entry.get("fy") == fiscal_year
                    and _annual_form_base(entry.get("form")) is not None
                    and entry.get("val") is not None
                )

        if depreciation_only_candidates:
            candidate, unit, entry = max(
                depreciation_only_candidates,
                key=lambda item: _entry_sort_key((item[1], item[2])),
            )
            selected_evidence = _candidate_value(
                candidate, unit, entry, cik, facts_url
            )
            return AnnualFinancialValue(
                financial_field=definition.name,
                financial_statement=definition.statement,
                fiscal_year=fiscal_year,
                status=FactStatus.NEEDS_VALIDATION,
                raw_value=None,
                filing_form=selected_evidence.filing_form,
                filing_date=selected_evidence.filing_date,
                accession_number=selected_evidence.accession_number,
                source_url=selected_evidence.source_url,
                sec_source_identifier=(
                    f"CIK{cik}:{selected_evidence.accession_number or 'companyfacts'}"
                ),
                xbrl_taxonomy=selected_evidence.xbrl_taxonomy,
                xbrl_concept=selected_evidence.xbrl_concept,
                unit=selected_evidence.unit,
                period_start=selected_evidence.period_start,
                period_end=selected_evidence.period_end,
                validation_reason=(
                    "The available SEC concept reports depreciation only and cannot "
                    "populate Depreciation & Amortization; no amortization was "
                    "substituted or estimated."
                ),
                candidate_values=tuple(
                    _candidate_value(item_candidate, item_unit, item_entry, cik, facts_url)
                    for item_candidate, item_unit, item_entry
                    in depreciation_only_candidates
                ),
            )

    return AnnualFinancialValue(
        financial_field=definition.name,
        financial_statement=definition.statement,
        fiscal_year=fiscal_year,
        status=FactStatus.MISSING,
        source_url=facts_url,
        sec_source_identifier=f"CIK{cik}:companyfacts",
        missing_reason=(
            "No valid annual 10-K, 20-F, or 40-F fact was found for any approved "
            "XBRL concept; no value was guessed."
        ),
    )


def fetch_annual_financial_statements(
    company: Union[CompanyIdentity, str],
    *,
    user_agent: str,
    fiscal_years: Optional[Iterable[int]] = None,
) -> AnnualFinancialStatements:
    """Convenience entry point using the official SEC network endpoints."""

    return SECFinancialStatementFetcher(user_agent).fetch(
        company, fiscal_years=fiscal_years
    )
