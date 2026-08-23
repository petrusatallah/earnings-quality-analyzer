"""Tests for Task 71 company identification."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.company_identifier import (  # noqa: E402
    CompanyIdentity,
    IdentificationStatus,
    identify_company,
    normalize_ticker_input,
)


def test_task_71_company_identification() -> None:
    assert identify_company("AAPL").company.ticker == "AAPL"
    assert identify_company("apple").company.ticker == "AAPL"
    assert identify_company("Apple Inc.").company.ticker == "AAPL"
    assert identify_company("  aPpLe   iNc.  ").company.ticker == "AAPL"
    assert identify_company("Microsoft Corporation").company.ticker == "MSFT"

    google = identify_company("Google")
    assert google.status is IdentificationStatus.AMBIGUOUS
    assert {candidate.ticker for candidate in google.candidates} == {"GOOG", "GOOGL"}

    googl = identify_company("GOOGL")
    assert googl.status is IdentificationStatus.MATCHED
    assert googl.company.ticker == "GOOGL"
    assert "Alphabet Class A" in googl.company.aliases

    goog = identify_company("GOOG")
    assert goog.status is IdentificationStatus.MATCHED
    assert goog.company.ticker == "GOOG"
    assert "Alphabet Class C" in goog.company.aliases

    unsupported = identify_company("Unsupported Company")
    assert unsupported.status is IdentificationStatus.NOT_FOUND
    assert unsupported.company is None


def test_punctuated_tickers_are_preserved_and_matched_exactly() -> None:
    companies = (
        CompanyIdentity("Example Class B", "BRK.B"),
        CompanyIdentity("Example Dash Listing", "BRK-B"),
    )

    assert normalize_ticker_input(" brk.b ") == "BRK.B"
    assert normalize_ticker_input(" brk-b ") == "BRK-B"
    assert identify_company("BRK.B", companies=companies).company.ticker == "BRK.B"
    assert identify_company("BRK-B", companies=companies).company.ticker == "BRK-B"


if __name__ == "__main__":
    test_task_71_company_identification()
    test_punctuated_tickers_are_preserved_and_matched_exactly()
    print("Task 71 company identifier tests passed")
