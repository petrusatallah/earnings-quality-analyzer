"""Standardize ticker or company-name input without fetching financial data.

The resolver is deliberately separated from any remote lookup implementation.
Later tasks can supply an official lookup source implementing ``CompanyLookupSource``.
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Iterable, Optional, Protocol, Sequence, Tuple


class IdentificationStatus(str, Enum):
    """Possible outcomes of a company identification request."""

    MATCHED = "Matched"
    AMBIGUOUS = "Ambiguous"
    NOT_FOUND = "Unsupported/Not Found"


@dataclass(frozen=True)
class CompanyIdentity:
    """A standardized public-company identity."""

    company_name: str
    ticker: str
    exchange: Optional[str] = None
    country: Optional[str] = None
    regulator: Optional[str] = None
    aliases: Tuple[str, ...] = field(default_factory=tuple, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", self.ticker.strip().upper())


@dataclass(frozen=True)
class IdentificationResult:
    """A match, an ambiguity with candidates, or a not-found result."""

    status: IdentificationStatus
    company: Optional[CompanyIdentity] = None
    candidates: Tuple[CompanyIdentity, ...] = ()
    message: str = ""

    @property
    def matched(self) -> bool:
        return self.status is IdentificationStatus.MATCHED


class CompanyLookupSource(Protocol):
    """Interface for a future official company/ticker lookup source."""

    def find_candidates(self, query: str) -> Iterable[CompanyIdentity]:
        """Return all plausible candidates; do not choose between duplicates."""


_LEGAL_SUFFIXES = {
    "ag",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "limited",
    "llc",
    "ltd",
    "nv",
    "plc",
    "sa",
}


def normalize_company_input(value: str) -> str:
    """Normalize case, surrounding space, punctuation, and repeated spacing."""

    if not isinstance(value, str):
        return ""
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def normalize_ticker_input(value: str) -> str:
    """Normalize a possible ticker while preserving ``.`` and ``-``.

    An empty string means the input is not shaped like a ticker. Ticker
    punctuation is significant: for example, ``BRK.B`` and ``BRK-B`` remain
    distinct identifiers.
    """

    if not isinstance(value, str):
        return ""
    ticker = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]+(?:[.-][A-Z0-9]+)*", ticker):
        return ""
    return ticker


def _name_without_legal_suffix(value: str) -> str:
    words = normalize_company_input(value).split()
    while words and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def _company_name_keys(company: CompanyIdentity) -> set[str]:
    keys: set[str] = set()
    for name in (company.company_name, *company.aliases):
        normalized = normalize_company_input(name)
        if normalized:
            keys.add(normalized)
        shortened = _name_without_legal_suffix(name)
        if shortened:
            keys.add(shortened)
    return keys


class InMemoryCompanyLookup:
    """Deterministic local lookup useful for validation and injected datasets."""

    def __init__(self, companies: Iterable[CompanyIdentity]) -> None:
        self._companies = tuple(companies)

    def find_candidates(self, query: str) -> Iterable[CompanyIdentity]:
        ticker_query = normalize_ticker_input(query)
        if ticker_query:
            ticker_matches = tuple(
                company
                for company in self._companies
                if normalize_ticker_input(company.ticker) == ticker_query
            )
            if ticker_matches:
                return ticker_matches

        name_query = normalize_company_input(query)
        shortened_query = _name_without_legal_suffix(name_query)
        if not name_query:
            return ()
        return tuple(
            company
            for company in self._companies
            if name_query in _company_name_keys(company)
            or (shortened_query and shortened_query in _company_name_keys(company))
        )


# Small deterministic fixtures for offline identifier tests. The live selector
# is loaded from the official SEC company-ticker endpoint, not from this tuple.
VALIDATION_COMPANIES: Tuple[CompanyIdentity, ...] = (
    CompanyIdentity("Apple Inc.", "AAPL", "NASDAQ", "United States", "SEC", ("Apple",)),
    CompanyIdentity("Microsoft Corporation", "MSFT", "NASDAQ", "United States", "SEC", ("Microsoft",)),
    CompanyIdentity("Amazon.com, Inc.", "AMZN", "NASDAQ", "United States", "SEC", ("Amazon",)),
    CompanyIdentity("Alphabet Inc.", "GOOGL", "NASDAQ", "United States", "SEC", ("Google", "Alphabet Class A")),
    CompanyIdentity("Alphabet Inc.", "GOOG", "NASDAQ", "United States", "SEC", ("Google", "Alphabet Class C")),
)


def identify_company(
    user_input: str,
    *,
    lookup_source: Optional[CompanyLookupSource] = None,
    companies: Optional[Sequence[CompanyIdentity]] = None,
) -> IdentificationResult:
    """Resolve input without guessing when zero or multiple companies match.

    Pass ``lookup_source`` to connect an official lookup service later, or pass
    ``companies`` for a local dataset. Supplying both is invalid.
    """

    if lookup_source is not None and companies is not None:
        raise ValueError("Provide either lookup_source or companies, not both.")

    query = user_input.strip() if isinstance(user_input, str) else ""
    if not normalize_company_input(query):
        return IdentificationResult(
            IdentificationStatus.NOT_FOUND,
            message="Unsupported/not found: enter a ticker or company name.",
        )

    source = lookup_source or InMemoryCompanyLookup(
        VALIDATION_COMPANIES if companies is None else companies
    )
    candidates = tuple(dict.fromkeys(source.find_candidates(query)))

    if len(candidates) == 1:
        return IdentificationResult(
            IdentificationStatus.MATCHED,
            company=candidates[0],
            candidates=candidates,
            message="Company identified.",
        )
    if len(candidates) > 1:
        return IdentificationResult(
            IdentificationStatus.AMBIGUOUS,
            candidates=candidates,
            message="Ambiguous company input; select one of the returned candidates.",
        )
    return IdentificationResult(
        IdentificationStatus.NOT_FOUND,
        message="Unsupported/not found: no matching public company was found.",
    )
