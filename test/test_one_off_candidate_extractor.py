"""Live and synthetic tests for Task 81 potential one-off candidates."""

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.company_identifier import IdentificationStatus, identify_company  # noqa: E402
from Data.financial_statement_fetcher import SECFinancialStatementFetcher  # noqa: E402
from Data.one_off_candidate_extractor import (  # noqa: E402
    OfficialFilingDocument,
    OneOffStatus,
    extract_potential_one_offs,
    retrieve_official_annual_filing_document,
)


def _user_agent() -> str:
    value = os.environ.get("SEC_USER_AGENT", "").strip()
    if not value:
        raise RuntimeError(
            "Set SEC_USER_AGENT to an identifying application name and real "
            "contact email before running this live SEC test."
        )
    return value


def test_task_81_apple_2024_state_aid_candidate() -> None:
    identity = identify_company("AAPL")
    assert identity.status is IdentificationStatus.MATCHED
    assert identity.company is not None
    fetcher = SECFinancialStatementFetcher(_user_agent())
    statements = fetcher.fetch(identity.company, fiscal_years=(2024,))
    document = retrieve_official_annual_filing_document(fetcher, statements, 2024)
    candidates = extract_potential_one_offs(
        identity.company, 2024, statements, document
    )

    state_aid = tuple(
        candidate
        for candidate in candidates
        if "state aid" in (
            f"{candidate.candidate_name} {candidate.source_evidence or ''}"
        ).casefold()
    )
    assert len(state_aid) == 1
    candidate = state_aid[0]
    assert candidate.status is OneOffStatus.CANDIDATE_FOUND
    assert candidate.raw_amount == 10_200_000_000
    assert candidate.raw_unit == "USD"
    assert candidate.normalized_usd_millions == 10_200
    assert candidate.impact_direction == "Decreases income / increases expense"
    assert candidate.filing_form == "10-K"
    assert candidate.accession_number == "0000320193-24-000123"
    assert candidate.source_url == document.source_url
    assert candidate.source_evidence

    _print_candidate("AAPL", candidate)
    print("Task 81 Apple 2024 State Aid candidate test passed")


def test_task_81_latest_msft_and_amzn_candidates() -> None:
    for ticker in ("MSFT", "AMZN"):
        identity = identify_company(ticker)
        assert identity.status is IdentificationStatus.MATCHED
        assert identity.company is not None
        fetcher = SECFinancialStatementFetcher(_user_agent())
        statements = fetcher.fetch(identity.company)
        fiscal_year = max(value.fiscal_year for value in statements.values)
        document = retrieve_official_annual_filing_document(
            fetcher, statements, fiscal_year
        )
        candidates = extract_potential_one_offs(
            identity.company, fiscal_year, statements, document
        )
        assert candidates
        assert all(
            item.status
            in {
                OneOffStatus.CANDIDATE_FOUND,
                OneOffStatus.NEEDS_VALIDATION,
                OneOffStatus.NONE_FOUND,
            }
            for item in candidates
        )
        for candidate in candidates:
            _print_candidate(ticker, candidate)
        print(f"Task 81 {ticker} candidate scan passed")


def _print_candidate(ticker, candidate) -> None:
    print(f"Ticker: {ticker}")
    print(f"Fiscal year: {candidate.fiscal_year}")
    print(f"Candidate: {candidate.candidate_name}")
    print(f"Category: {candidate.category or 'N/A'}")
    print(f"Amount: {candidate.raw_amount if candidate.raw_amount is not None else 'N/A'}")
    print(f"Raw unit: {candidate.raw_unit or 'N/A'}")
    print(
        "Normalized USD millions: "
        f"{candidate.normalized_usd_millions if candidate.normalized_usd_millions is not None else 'N/A'}"
    )
    print(f"Impact direction: {candidate.impact_direction or 'N/A'}")
    print(f"XBRL concept: {candidate.xbrl_concept or 'N/A'}")
    print(f"Filing section/note: {candidate.filing_section_or_note or 'N/A'}")
    print(f"Source: {candidate.source_url or 'N/A'}")
    print(f"Evidence: {candidate.source_evidence or 'N/A'}")
    print(f"Status: {candidate.status.value}")


def _synthetic_document(content: str, *, unit_ticker="EXM") -> OfficialFilingDocument:
    return OfficialFilingDocument(
        company_name="Example Corporation",
        ticker=unit_ticker,
        cik="0000000001",
        fiscal_year=2025,
        filing_form="10-K",
        filing_date="2026-02-15",
        accession_number="0000000001-26-000001",
        source_url="https://www.sec.gov/Archives/edgar/data/1/example.htm",
        content=content,
    )


class _Statements:
    ticker = "EXM"


def test_duplicate_event_disclosure_is_deduplicated() -> None:
    text = (
        "<div>The company recorded a one-time restructuring charge of $25 million "
        "related to Program Alpha.</div>"
        "<div>A one-time restructuring charge of $25 million related to Program Alpha "
        "was recorded.</div>"
    )
    candidates = extract_potential_one_offs(
        "EXM", 2025, _Statements(), _synthetic_document(text)
    )
    assert len(candidates) == 1
    assert candidates[0].status is OneOffStatus.CANDIDATE_FOUND


def test_unusual_wording_without_amount_needs_validation() -> None:
    candidates = extract_potential_one_offs(
        "EXM",
        2025,
        _Statements(),
        _synthetic_document("<p>The company incurred an unusual restructuring charge.</p>"),
    )
    assert len(candidates) == 1
    assert candidates[0].status is OneOffStatus.NEEDS_VALIDATION
    assert candidates[0].raw_amount is None


def test_recurring_expense_is_not_a_one_off_candidate() -> None:
    candidates = extract_potential_one_offs(
        "EXM",
        2025,
        _Statements(),
        _synthetic_document(
            "<p>Recurring payroll expense was $500 million during the year and "
            "is expected to continue.</p>"
        ),
    )
    assert len(candidates) == 1
    assert candidates[0].status is OneOffStatus.NONE_FOUND


def test_conflicting_candidate_amounts_need_validation() -> None:
    document = _synthetic_document(
        "<p>A one-time litigation charge of $20 million related to Case Alpha.</p>"
        "<p>A one-time litigation charge of $30 million related to Case Alpha.</p>"
    )
    candidates = extract_potential_one_offs("EXM", 2025, _Statements(), document)
    assert len(candidates) == 1
    assert candidates[0].status is OneOffStatus.NEEDS_VALIDATION
    assert candidates[0].raw_amount is None
    assert "Conflicting" in candidates[0].validation_reason


def test_non_usd_amount_is_preserved_without_usd_normalization() -> None:
    candidates = extract_potential_one_offs(
        "EXM",
        2025,
        _Statements(),
        _synthetic_document(
            "<p>A one-time restructuring charge of €50 million related to Program Beta.</p>"
        ),
    )
    assert len(candidates) == 1
    assert candidates[0].raw_amount == 50_000_000
    assert candidates[0].raw_unit == "EUR"
    assert candidates[0].normalized_usd_millions is None


def test_hypothetical_and_general_risk_language_is_rejected() -> None:
    text = (
        "<p>We may be subject to fines and settlements if regulators determine "
        "that our privacy practices violate applicable law.</p>"
        "<p>If the carrying value is not recoverable, we recognize an impairment "
        "loss under our accounting policy.</p>"
        "<p>Cybersecurity incidents could result in litigation, fines, losses, "
        "and reputational harm.</p>"
        "<p>The final resolution of litigation may differ from the amounts "
        "recorded in our financial statements.</p>"
        "<p>Once an investment is determined to be impaired, an impairment "
        "charge is recorded in other expense.</p>"
        "<p>If we have plans to sell the security or it is more likely than not "
        "that market conditions will require a sale before the expected recovery "
        "of its full carrying value, then the decline below cost is recorded as "
        "an impairment charge.</p>"
    )
    candidates = extract_potential_one_offs(
        "EXM", 2025, _Statements(), _synthetic_document(text)
    )
    assert len(candidates) == 1
    assert candidates[0].status is OneOffStatus.NONE_FOUND


def test_same_ftc_settlement_disclosed_twice_is_deduplicated() -> None:
    text = (
        "<p>We entered into an agreement with the FTC and incurred a $2.5 billion "
        "legal settlement charge related to the FTC consumer protection matter.</p>"
        "<p>The company recorded a legal settlement charge of $2.5 billion related "
        "to the FTC consumer protection matter.</p>"
    )
    candidates = extract_potential_one_offs(
        "EXM", 2025, _Statements(), _synthetic_document(text)
    )
    assert len(candidates) == 1
    assert candidates[0].raw_amount == 2_500_000_000
    assert "FTC" in candidates[0].source_evidence


def test_bundled_amount_is_not_assigned_to_one_component_category() -> None:
    candidates = extract_potential_one_offs(
        "EXM",
        2025,
        _Statements(),
        _synthetic_document(
            "<p>We recorded $2.4 billion of charges related to settlements of a "
            "lawsuit and tax disputes, severance costs, and asset impairments.</p>"
        ),
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.category == "Bundled Unusual Items"
    assert candidate.status is OneOffStatus.NEEDS_VALIDATION
    assert candidate.raw_amount == 2_400_000_000
    assert "multiple unusual components" in candidate.validation_reason


def test_foreign_currency_settlement_wording_is_not_litigation() -> None:
    candidates = extract_potential_one_offs(
        "EXM",
        2025,
        _Statements(),
        _synthetic_document(
            "<p>In connection with settlement and remeasurement of intercompany "
            "balances, we recorded foreign-currency gains of $413 million.</p>"
        ),
    )
    assert len(candidates) == 1
    assert candidates[0].status is OneOffStatus.NONE_FOUND


def test_actual_euro_regulatory_fine_is_preserved() -> None:
    candidates = extract_potential_one_offs(
        "EXM",
        2025,
        _Statements(),
        _synthetic_document(
            "<p>The commission decision imposed a regulatory fine of EUR 1.13 "
            "billion, which the company incurred during the year.</p>"
        ),
    )
    assert len(candidates) == 1
    assert candidates[0].raw_amount == 1_130_000_000
    assert candidates[0].raw_unit == "EUR"
    assert candidates[0].normalized_usd_millions is None
    assert candidates[0].status is OneOffStatus.NEEDS_VALIDATION
    assert "earnings is unclear" in candidates[0].validation_reason


def test_level_three_accounting_policy_is_not_an_actual_impairment() -> None:
    candidates = extract_potential_one_offs(
        "EXM",
        2025,
        _Statements(),
        _synthetic_document(
            "<p>Our Level 3 assets and liabilities include financial instruments "
            "when they are recorded at fair value due to an impairment charge.</p>"
        ),
    )
    assert len(candidates) == 1
    assert candidates[0].status is OneOffStatus.NONE_FOUND


def test_partially_bundled_tax_dispute_and_lawsuit_amount_needs_validation() -> None:
    candidates = extract_potential_one_offs(
        "EXM",
        2025,
        _Statements(),
        _synthetic_document(
            "<p>We recorded $1.1 billion of expense related to the resolution of "
            "tax disputes and the settlement of a lawsuit.</p>"
        ),
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.category == "Bundled Unusual Items"
    assert candidate.status is OneOffStatus.NEEDS_VALIDATION
    assert candidate.raw_amount == 1_100_000_000


def test_event_without_current_year_earnings_effect_needs_validation() -> None:
    candidates = extract_potential_one_offs(
        "EXM",
        2025,
        _Statements(),
        _synthetic_document(
            "<p>The regulator imposed a fine of $75 million, which we paid while "
            "continuing our appeal.</p>"
        ),
    )
    assert len(candidates) == 1
    assert candidates[0].raw_amount == 75_000_000
    assert candidates[0].status is OneOffStatus.NEEDS_VALIDATION
    assert "earnings is unclear" in candidates[0].validation_reason


if __name__ == "__main__":
    test_duplicate_event_disclosure_is_deduplicated()
    test_unusual_wording_without_amount_needs_validation()
    test_recurring_expense_is_not_a_one_off_candidate()
    test_conflicting_candidate_amounts_need_validation()
    test_non_usd_amount_is_preserved_without_usd_normalization()
    test_hypothetical_and_general_risk_language_is_rejected()
    test_same_ftc_settlement_disclosed_twice_is_deduplicated()
    test_bundled_amount_is_not_assigned_to_one_component_category()
    test_foreign_currency_settlement_wording_is_not_litigation()
    test_actual_euro_regulatory_fine_is_preserved()
    test_level_three_accounting_policy_is_not_an_actual_impairment()
    test_partially_bundled_tax_dispute_and_lawsuit_amount_needs_validation()
    test_event_without_current_year_earnings_effect_needs_validation()
    test_task_81_apple_2024_state_aid_candidate()
    test_task_81_latest_msft_and_amzn_candidates()
