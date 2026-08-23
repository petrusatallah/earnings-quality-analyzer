"""Focused tests for Task 112's curated supported-company selector."""

from types import SimpleNamespace

import pytest

from main import (
    SUPPORTED_COMPANIES,
    available_fiscal_years,
    identify_official_company,
    search_supported_company_options,
    sec_company_options,
)


APPROVED_LABELS = (
    "Apple Inc. (AAPL)",
    "Microsoft Corporation (MSFT)",
    "NVIDIA Corporation (NVDA)",
    "Alphabet Inc. (GOOGL)",
    "Meta Platforms, Inc. (META)",
    "Adobe Inc. (ADBE)",
    "Salesforce, Inc. (CRM)",
    "Intel Corporation (INTC)",
    "Advanced Micro Devices, Inc. (AMD)",
    "Cisco Systems, Inc. (CSCO)",
    "Amazon.com, Inc. (AMZN)",
    "Walmart Inc. (WMT)",
    "Costco Wholesale Corporation (COST)",
    "The Home Depot, Inc. (HD)",
    "NIKE, Inc. (NKE)",
    "Starbucks Corporation (SBUX)",
    "McDonald's Corporation (MCD)",
    "The Coca-Cola Company (KO)",
    "PepsiCo, Inc. (PEP)",
    "Procter & Gamble Co. (PG)",
    "Caterpillar Inc. (CAT)",
    "Deere & Company (DE)",
    "Honeywell International Inc. (HON)",
    "3M Company (MMM)",
    "United Parcel Service, Inc. (UPS)",
    "FedEx Corporation (FDX)",
    "Union Pacific Corporation (UNP)",
    "General Electric Company (GE)",
    "RTX Corporation (RTX)",
    "Lockheed Martin Corporation (LMT)",
    "Tesla, Inc. (TSLA)",
    "General Motors Company (GM)",
    "Ford Motor Company (F)",
    "Exxon Mobil Corporation (XOM)",
    "Chevron Corporation (CVX)",
    "ConocoPhillips (COP)",
    "Johnson & Johnson (JNJ)",
    "Pfizer Inc. (PFE)",
    "Merck & Co., Inc. (MRK)",
    "Eli Lilly and Company (LLY)",
    "AbbVie Inc. (ABBV)",
    "Verizon Communications Inc. (VZ)",
    "AT&T Inc. (T)",
    "The Walt Disney Company (DIS)",
    "Netflix, Inc. (NFLX)",
    "Comcast Corporation (CMCSA)",
)


def _record(company_name, ticker):
    return SimpleNamespace(company_name=company_name, ticker=ticker)


class FakeFetcher:
    def __init__(self, records, *, years=()):
        self.records = tuple(records)
        self.years = tuple(years)
        self.resolved_queries = []

    def list_companies(self):
        return self.records

    def resolve_cik(self, query):
        ticker = getattr(query, "ticker", str(query)).upper()
        self.resolved_queries.append(ticker)
        for record in self.records:
            if record.ticker == ticker:
                return record
        raise LookupError(f"{ticker} is unavailable")

    def fetch(self, company):
        self.resolve_cik(company)
        values = tuple(
            SimpleNamespace(fiscal_year=year, raw_value=1.0) for year in self.years
        )
        return SimpleNamespace(values=values)


def _labels(options):
    return tuple(f"{item.company_name} ({item.ticker})" for item in options)


def test_only_the_exact_approved_companies_can_appear():
    official_records = [
        _record(company.company_name, company.ticker)
        for company in SUPPORTED_COMPANIES
    ]
    official_records.extend(
        (_record("JPMorgan Chase & Co.", "JPM"), _record("Example SPAC", "SPCX"))
    )

    assert _labels(sec_company_options(fetcher=FakeFetcher(official_records))) == APPROVED_LABELS


def test_search_matches_company_name_and_ticker():
    options = sec_company_options(
        fetcher=FakeFetcher(
            (_record("Apple SEC title", "AAPL"), _record("UPS SEC title", "UPS"))
        )
    )

    assert _labels(search_supported_company_options("parcel", options)) == (
        "United Parcel Service, Inc. (UPS)",
    )
    assert _labels(search_supported_company_options("aapl", options)) == (
        "Apple Inc. (AAPL)",
    )


def test_unavailable_approved_companies_are_excluded_or_fail_safely():
    options = sec_company_options(fetcher=FakeFetcher((_record("Apple", "AAPL"),)))
    assert _labels(options) == ("Apple Inc. (AAPL)",)

    short_history = FakeFetcher((_record("Apple", "AAPL"),), years=(2023, 2024, 2025))
    assert len(available_fiscal_years("AAPL", fetcher=short_history)) < 4

    unresolved = FakeFetcher(())
    with pytest.raises(LookupError):
        available_fiscal_years("AAPL", fetcher=unresolved)


def test_selected_company_is_verified_by_the_sec_lookup():
    fetcher = FakeFetcher((_record("Apple Inc.", "AAPL"),))

    company = identify_official_company("Apple Inc.", fetcher=fetcher)

    assert company.ticker == "AAPL"
    assert fetcher.resolved_queries == ["AAPL"]


def test_unapproved_sec_company_never_appears():
    options = sec_company_options(
        fetcher=FakeFetcher(
            (_record("JPMorgan Chase & Co.", "JPM"), _record("Apple", "AAPL"))
        )
    )

    assert _labels(options) == ("Apple Inc. (AAPL)",)
