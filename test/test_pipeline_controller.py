"""Focused Task 109 tests for the ordered pipeline controller."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.analysis_validation_gate import (  # noqa: E402
    AnalysisDecision,
    AnalysisValidationGateResult,
    BlockingIssue,
)
import main as pipeline_main  # noqa: E402
from main import (  # noqa: E402
    PipelineModules,
    _apply_correction_overlay,
    _restore_normalization_fiscal_years,
    create_production_pipeline_modules,
    identify_official_company,
    run_pipeline,
    sec_company_options,
)
from Data.financial_statement_fetcher import (  # noqa: E402
    SECFinancialStatementFetcher,
    SEC_TICKER_URL,
)
from Data.manual_corrections import (  # noqa: E402
    create_manual_correction,
    effective_value,
)
from Data.apple_test_dataset import apple_financial_data_df  # noqa: E402
from Analysis.manual_one_off_classification import (  # noqa: E402
    manual_one_off_classification_df,
)
from Analysis.reporting_view_model import (  # noqa: E402
    ReportingInputEnvelope,
    build_reporting_view_model,
)


APPLE_BENCHMARK_DATA = apple_financial_data_df.copy(deep=True)
APPLE_ONE_OFF_FIXTURE = manual_one_off_classification_df.copy(deep=True)


def gate(*, can_analyze: bool) -> AnalysisValidationGateResult:
    issue = BlockingIssue(
        metric="Revenue",
        fiscal_year=2024,
        validation_source="Task 83 missing-data validation",
        blocking_status="MISSING",
        explanation="Required value is unavailable.",
        manual_correction_used=False,
    )
    issues = () if can_analyze else (issue,)
    return AnalysisValidationGateResult(
        decision=(
            AnalysisDecision.CONTINUE if can_analyze else AnalysisDecision.STOP
        ),
        can_analyze=can_analyze,
        requested_fiscal_years=(2023, 2024),
        blocking_issues=issues,
        metric_year_results=(),
        blocking_issue_count=len(issues),
    )


def partial_company_frame(*, inventory_2024=None, da_2024=44.0) -> pd.DataFrame:
    values = {
        "Revenue": [1_000.0, 1_100.0, 1_210.0, 1_331.0],
        "Net Income": [100.0, 110.0, 121.0, 133.1],
        "Operating Cash Flow": [150.0, 165.0, 181.5, 199.65],
        "Accounts Receivable": [100.0, 105.0, 110.0, 115.0],
        "Inventory": [80.0, 82.0, inventory_2024, 86.0],
        "Accounts Payable": [70.0, 75.0, 80.0, 85.0],
        "Depreciation & Amortization": [40.0, 42.0, da_2024, 46.0],
        "Capital Expenditures": [50.0, 52.0, 54.0, 56.0],
        "Stock-Based Compensation": [5.0, 5.5, 6.0, 6.5],
        "Shares Outstanding": [100.0, 100.5, 101.0, 101.5],
        "Deferred Tax Assets": [20.0, 21.0, 22.0, 23.0],
        "Deferred Tax Liabilities": [10.0, 11.0, 12.0, 13.0],
        "Tax Expense": [20.0, 22.0, 24.0, 26.0],
    }
    return pd.DataFrame(
        [
            {
                "Company": "Partial Data Industries",
                "Ticker": "PART",
                "Fiscal Year": fiscal_year,
                "Metric": metric,
                "Value": annual_values[position],
                "Units": (
                    "shares millions"
                    if metric == "Shares Outstanding"
                    else "USD millions"
                ),
                "Financial Statement": "Reviewed test fixture",
                "Source": "https://www.sec.gov/Archives/partial",
                "Source Date": "2026-01-01",
            }
            for position, fiscal_year in enumerate((2022, 2023, 2024, 2025))
            for metric, annual_values in values.items()
        ]
    )


def test_pipeline_executes_existing_modules_in_required_order_and_passes_outputs():
    calls = []
    identity = object()
    extracted = object()
    approved_gate = gate(can_analyze=True)
    corrected = object()
    calculations = object()
    flags = object()
    structured = object()
    interpretations = object()
    workbook = object()
    corrections = (object(),)

    def identify(query):
        calls.append("identify")
        assert query == "AMZN"
        return identity

    def extract(company, years):
        calls.append("extract")
        assert company is identity
        assert years == 4
        return extracted

    def validate(data, years, supplied_corrections):
        calls.append("validate")
        assert data is extracted
        assert years == 4
        assert supplied_corrections == corrections
        return approved_gate

    def apply_corrections(data, supplied_corrections):
        calls.append("corrections")
        assert data is extracted
        assert supplied_corrections == corrections
        return corrected

    def calculate(data):
        calls.append("calculations")
        assert data is corrected
        return calculations

    def analyze(calculated):
        calls.append("red_flags_severity")
        assert calculated is calculations
        return flags

    def prepare(company, validation, data, calculated, analyzed):
        calls.append("structured_ai_input")
        assert (company, validation, data, calculated, analyzed) == (
            identity, approved_gate, corrected, calculations, flags
        )
        return structured

    def interpret(ai_input):
        calls.append("interpretations")
        assert ai_input is structured
        return interpretations

    def export(
        company, data, calculated, analyzed, ai_input, interpreted, validation
    ):
        calls.append("excel")
        assert (
            company,
            data,
            calculated,
            analyzed,
            ai_input,
            interpreted,
            validation,
        ) == (
            identity,
            corrected,
            calculations,
            flags,
            structured,
            interpretations,
            approved_gate,
        )
        return workbook

    modules = PipelineModules(
        identify, extract, validate, apply_corrections, calculate, analyze,
        prepare, interpret, export,
    )
    result = run_pipeline(
        "AMZN", 4, modules=modules, manual_corrections=corrections
    )

    assert calls == [
        "identify", "extract", "validate", "corrections", "calculations",
        "red_flags_severity", "structured_ai_input", "interpretations", "excel",
    ]
    assert result.blocked is False
    assert result.company is identity
    assert result.extracted_data is extracted
    assert result.validation is approved_gate
    assert result.corrected_data is corrected
    assert result.calculations is calculations
    assert result.red_flags_and_severity is flags
    assert result.structured_ai_input is structured
    assert result.interpretations is interpretations
    assert result.excel_output is workbook


def test_missing_validation_continues_downstream_analysis():
    calls = []
    identity = object()
    extracted = object()
    blocked_gate = gate(can_analyze=False)
    corrected = object()

    def identify(_query):
        calls.append("identify")
        return identity

    def extract(company, years):
        calls.append("extract")
        assert company is identity and years == 4
        return extracted

    def validate(data, years, corrections):
        calls.append("validate")
        assert data is extracted and years == 4 and corrections == ()
        return blocked_gate

    def correction_stage(data, corrections):
        calls.append("corrections")
        assert data is extracted and corrections == ()
        return corrected

    def calculate(data):
        calls.append("calculations")
        assert data is corrected
        return {"available_result": 42}

    def analyze(calculations):
        calls.append("analysis")
        assert calculations["available_result"] == 42
        return {"unrelated_rule": "available"}

    def prepare(*_args):
        calls.append("structured")
        return {"partial": True}

    def interpret(*_args):
        calls.append("interpretations")
        return {"partial": True}

    def export(*_args):
        calls.append("excel")
        return "partial.xlsx"

    modules = PipelineModules(
        identify, extract, validate, correction_stage, calculate, analyze,
        prepare, interpret, export,
    )
    result = run_pipeline("Amazon", 4, modules=modules)

    assert calls == [
        "identify", "extract", "validate", "corrections", "calculations",
        "analysis", "structured", "interpretations", "excel",
    ]
    assert result.blocked is False
    assert result.partial is True
    assert "Revenue (FY 2024)" in result.partial_notice
    assert "Correct Extracted Data panel" in result.partial_notice
    assert result.validation is blocked_gate
    assert result.calculations["available_result"] == 42
    assert result.red_flags_and_severity["unrelated_rule"] == "available"


def test_production_factory_configures_every_real_pipeline_stage(monkeypatch):
    verified_company = SimpleNamespace(
        company_name="Microsoft Corporation", ticker="MSFT"
    )
    fake_fetcher = SimpleNamespace(resolve_cik=lambda _query: verified_company)
    monkeypatch.setattr(
        pipeline_main,
        "_sec_fetcher",
        lambda _user_agent, fetcher=None: fetcher or fake_fetcher,
    )
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )

    assert isinstance(modules, PipelineModules)
    assert all(
        callable(stage)
        for stage in (
            modules.identify_company,
            modules.extract_data,
            modules.validate_data,
            modules.apply_manual_corrections,
            modules.run_calculations,
            modules.run_red_flags_and_severity,
            modules.build_structured_ai_input,
            modules.run_interpretations,
            modules.generate_excel,
        )
    )
    identified = modules.identify_company("Microsoft")
    assert identified.company_name == "Microsoft Corporation"
    assert identified.ticker == "MSFT"


def test_company_selector_options_come_from_official_sec_data_and_include_ups():
    payload = {
        "0": {
            "cik_str": 1090727,
            "ticker": "UPS",
            "title": "United Parcel Service, Inc.",
        },
        "1": {
            "cik_str": 320193,
            "ticker": "AAPL",
            "title": "Apple Inc.",
        },
    }

    def official_loader(url, _headers, _timeout):
        assert url == SEC_TICKER_URL
        return payload

    fetcher = SECFinancialStatementFetcher(
        "EarningsQualityAgent tests@example.com",
        minimum_request_interval=0.11,
        json_loader=official_loader,
    )
    options = sec_company_options(fetcher=fetcher)
    labels = [f"{company.company_name} ({company.ticker})" for company in options]

    assert labels == ["Apple Inc. (AAPL)", "United Parcel Service, Inc. (UPS)"]
    assert any("parcel" in label.casefold() for label in labels)
    assert any("ups" in label.casefold() for label in labels)
    ups = identify_official_company("UPS", fetcher=fetcher)
    assert ups.company_name == "United Parcel Service, Inc."
    assert ups.ticker == "UPS"
    assert ups.regulator == "SEC"


def test_non_apple_dataset_feeds_production_calculations_and_red_flags():
    values = {
        "Revenue": [1_000.0, 1_100.0, 1_210.0, 1_331.0],
        "Net Income": [100.0, 110.0, 121.0, 133.1],
        "Operating Cash Flow": [150.0, 165.0, 181.5, 199.65],
        "Accounts Receivable": [100.0, 105.0, 110.0, 115.0],
        "Inventory": [80.0, 82.0, 84.0, 86.0],
        "Accounts Payable": [70.0, 75.0, 80.0, 85.0],
        "Depreciation & Amortization": [40.0, 42.0, 44.0, 46.0],
        "Capital Expenditures": [50.0, 52.0, 54.0, 56.0],
        "Stock-Based Compensation": [5.0, 5.5, 6.0, 6.5],
        "Shares Outstanding": [100.0, 100.5, 101.0, 101.5],
        "Deferred Tax Assets": [20.0, 21.0, 22.0, 23.0],
        "Deferred Tax Liabilities": [10.0, 11.0, 12.0, 13.0],
        "Tax Expense": [20.0, 22.0, 24.0, 26.0],
    }
    records = []
    for position, fiscal_year in enumerate((2022, 2023, 2024, 2025)):
        for metric, annual_values in values.items():
            records.append({
                "Company": "Contoso Industries",
                "Ticker": "CTSO",
                "Fiscal Year": fiscal_year,
                "Metric": metric,
                "Value": annual_values[position],
                "Units": (
                    "shares millions"
                    if metric == "Shares Outstanding"
                    else "USD millions"
                ),
                "Financial Statement": "Reviewed test fixture",
                "Source": "https://www.sec.gov/Archives/contoso",
                "Source Date": "2026-01-01",
            })
    company_data = pd.DataFrame(records)
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )

    calculations = modules.run_calculations(company_data)
    analysis = modules.run_red_flags_and_severity(calculations)

    summary = calculations["financial_summary"].set_index("Fiscal Year")
    assert summary.loc[2025, "Revenue"] == 1_331.0
    assert summary.loc[2025, "Free Cash Flow"] == 143.65
    assert set(calculations["corrected_financial_data"]["Company"]) == {
        "Contoso Industries"
    }

    capex = analysis["red_flags"].loc[
        (analysis["red_flags"]["Fiscal Year"] == 2025)
        & (analysis["red_flags"]["Metric"] == "CapEx vs D&A")
    ].iloc[0]
    assert "CapEx = 56" in capex["Raw Data"]
    assert "D&A = 46" in capex["Raw Data"]
    assert not analysis["red_flags"].astype(str).apply(
        lambda column: column.str.contains("Apple|AAPL", case=False).any()
    ).any()

    # Gross issuance/repurchase evidence is not present in this supplied
    # dataset. It must remain missing rather than inheriting Apple's table.
    assert analysis["sbc"]["Shares Issued Net"].isna().all()
    assert analysis["sbc"]["Shares Repurchased"].isna().all()


def test_task_112_non_apple_normalization_contains_no_apple_evidence():
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )
    calculations = modules.run_calculations(partial_company_frame())

    normalized = calculations["normalized_earnings"]
    one_offs = calculations["excel_support_tables"]["manual_one_offs"]
    combined_text = " ".join(
        normalized.astype(str).to_numpy().ravel().tolist()
        + one_offs.astype(str).to_numpy().ravel().tolist()
    ).casefold()

    for apple_evidence in (
        "apple", "aapl", "state aid", "10,200", "10200",
        "unusual tax gains/losses",
    ):
        assert apple_evidence not in combined_text
    assert set(one_offs["Company"]) == {"Partial Data Industries"}
    assert set(one_offs["Ticker"]) == {"PART"}
    assert set(one_offs["Category"]) == {"Unavailable"}
    assert one_offs["Value"].isna().all()


def test_task_112_unavailable_normalization_evidence_stays_unavailable():
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )
    calculations = modules.run_calculations(partial_company_frame())
    normalized = calculations["normalized_earnings"]

    assert normalized["Normalized Net Income"].isna().all()
    assert normalized["Difference"].isna().all()
    assert normalized["Percentage Difference"].isna().all()
    assert normalized["Large Normalization Difference Flag"].isna().all()
    assert normalized["Repeated One-Off Flag"].isna().all()
    assert normalized["Normalization Signal"].eq("Unavailable").all()
    assert normalized["One-Off Categories Identified"].eq("Unavailable").all()


def test_unavailable_one_off_state_reaches_flags_severity_structured_and_reporting():
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )
    corrected = partial_company_frame(inventory_2024=84.0)
    calculations = modules.run_calculations(corrected)
    analysis = modules.run_red_flags_and_severity(calculations)
    company = SimpleNamespace(
        company_name="Partial Data Industries", ticker="PART"
    )
    validation = AnalysisValidationGateResult(
        decision=AnalysisDecision.CONTINUE,
        can_analyze=True,
        requested_fiscal_years=(2022, 2023, 2024, 2025),
        blocking_issues=(),
        metric_year_results=(),
        blocking_issue_count=0,
    )
    structured = modules.build_structured_ai_input(
        company, validation, corrected, calculations, analysis
    )
    interpretations = modules.run_interpretations(structured)

    repeated = analysis["red_flags"].loc[
        analysis["red_flags"]["Metric"].eq("Repeated one-off items")
    ]
    assert len(repeated) == 3
    assert repeated[["Raw Data", "Calculation", "Result", "Severity"]].eq(
        "Unavailable"
    ).all().all()
    assert repeated["Explanation"].str.contains(
        "not independently available", case=False
    ).all()
    forbidden = "No Flag|Low Risk|No repeated pattern detected|No unusual items identified"
    assert not repeated.astype(str).apply(
        lambda column: column.str.contains(forbidden, case=False, regex=True).any()
    ).any()

    detailed = analysis["detailed_severity"].loc[
        analysis["detailed_severity"]["Metric"].eq("Repeated one-off items")
    ]
    assert detailed["Final Severity"].eq("Unavailable").all()
    fiscal = analysis["fiscal_year_severity"].set_index("Fiscal Year")
    assert fiscal["Unavailable Count"].eq(2).all()
    assert not fiscal["Triggered Metrics"].str.contains(
        "Repeated one-off items", regex=False
    ).any()
    assert (
        fiscal[
            [
                "Material Concern Count",
                "Needs Investigation Count",
                "Low Risk Count",
                "Unavailable Count",
            ]
        ].sum(axis=1)
        == 13
    ).all()
    assert analysis["overall_severity"].iloc[0]["Availability"] == "Partial"
    assert analysis["overall_severity"].iloc[0]["Benchmark Severity"] != "Low Risk"

    structured_repeated = [
        row for row in structured["red_flags"]
        if row["Metric"] == "Repeated one-off items"
    ]
    assert len(structured_repeated) == 3
    assert all(row["Result"] == "Unavailable" for row in structured_repeated)
    assert all(row["Severity"] == "Unavailable" for row in structured_repeated)

    view = build_reporting_view_model(
        ReportingInputEnvelope(
            company=company,
            validation=validation,
            corrected_data=corrected,
            calculations=calculations,
            red_flags_and_severity=analysis,
            structured_ai_input=structured,
            interpretations=interpretations,
        )
    )
    repeated_view = [
        row for row in view.unavailable_rules
        if row.metric == "Repeated one-off items"
    ]
    assert len(repeated_view) == 3
    assert all(row.result == "Unavailable" for row in repeated_view)
    assert all(row.final_severity == "Unavailable" for row in repeated_view)
    assert all(
        row.metric != "Repeated one-off items"
        for row in view.triggered_red_flags
    )


def test_explicit_but_unavailable_one_off_evidence_stays_unavailable():
    unavailable_fixture = APPLE_ONE_OFF_FIXTURE.copy(deep=True)
    unavailable_fixture["Availability"] = "Not Available"
    unavailable_fixture["Value"] = float("nan")
    unavailable_fixture["Manual Classification"] = "Not Applicable"
    unavailable_fixture["Manual Review Status"] = "Not Applicable"
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com",
        one_off_evidence=unavailable_fixture,
    )

    calculations = modules.run_calculations(
        APPLE_BENCHMARK_DATA.copy(deep=True)
    )
    normalized = calculations["normalized_earnings"]

    assert normalized["Normalized Net Income"].isna().all()
    assert normalized["Difference"].isna().all()
    assert normalized["Normalization Signal"].eq("Unavailable").all()


def test_explicit_apple_normalization_fixture_is_unchanged_after_non_apple_run():
    production_modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )
    production_modules.run_calculations(partial_company_frame())
    benchmark_modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com",
        one_off_evidence=APPLE_ONE_OFF_FIXTURE.copy(deep=True),
    )
    calculations = benchmark_modules.run_calculations(
        APPLE_BENCHMARK_DATA.copy(deep=True)
    )
    analysis = benchmark_modules.run_red_flags_and_severity(calculations)

    normalized = calculations["normalized_earnings"].set_index("Fiscal Year")
    assert normalized["Normalized Net Income"].to_dict() == {
        2022: 99803,
        2023: 96995,
        2024: 103936,
        2025: 112010,
    }
    assert normalized["Difference"].to_dict() == {
        2022: 0,
        2023: 0,
        2024: 10200,
        2025: 0,
    }
    assert normalized.loc[2024, "One-Off Categories Identified"] == (
        "Unusual tax gains/losses"
    )
    assert normalized.loc[2024, "Overall Severity"] == "Medium"
    repeated = analysis["red_flags"].loc[
        analysis["red_flags"]["Metric"].eq("Repeated one-off items")
    ]
    assert repeated["Result"].eq("No Flag").all()
    assert repeated["Severity"].eq("None").all()
    expected_explanations = normalized["Explanation"].to_dict()
    assert repeated.set_index("Fiscal Year")["Explanation"].to_dict() == {
        year: expected_explanations[year] for year in (2023, 2024, 2025)
    }
    assert analysis["overall_severity"].iloc[0]["Benchmark Severity"] == (
        "Material Concern"
    )


def test_five_year_apple_production_run_does_not_shift_benchmark_evidence():
    prior_year = APPLE_BENCHMARK_DATA.loc[
        APPLE_BENCHMARK_DATA["Fiscal Year"].eq(2022)
    ].copy(deep=True)
    prior_year["Fiscal Year"] = 2021
    five_year_apple = pd.concat(
        [prior_year, APPLE_BENCHMARK_DATA.copy(deep=True)], ignore_index=True
    )
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )

    calculations = modules.run_calculations(five_year_apple)
    normalized = calculations["normalized_earnings"].set_index("Fiscal Year")
    one_offs = calculations["excel_support_tables"]["manual_one_offs"]

    assert normalized.index.tolist() == [2021, 2022, 2023, 2024, 2025]
    assert normalized["Normalized Net Income"].isna().all()
    assert normalized["Difference"].isna().all()
    assert normalized["Normalization Signal"].eq("Unavailable").all()
    assert set(one_offs["Category"]) == {"Unavailable"}
    assert one_offs["Value"].isna().all()
    assert not one_offs.astype(str).apply(
        lambda column: column.str.contains("10200|State Aid", case=False).any()
    ).any()


def test_apple_ticker_alone_does_not_import_benchmark_one_off_data(monkeypatch):
    imported = []
    original_import_module = pipeline_main.importlib.import_module

    def tracking_import(name, *args, **kwargs):
        imported.append(name)
        return original_import_module(name, *args, **kwargs)

    monkeypatch.setattr(pipeline_main.importlib, "import_module", tracking_import)
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )
    calculations = modules.run_calculations(
        APPLE_BENCHMARK_DATA.copy(deep=True)
    )

    assert "Data.one_off_items" not in imported
    assert "Data.manual_verified_answer_sheet" not in imported
    assert calculations["normalized_earnings"][
        "Normalization Signal"
    ].eq("Unavailable").all()


def test_task_112_mapped_normalization_text_uses_actual_fiscal_years():
    canonical = pd.DataFrame(
        [
            {
                "Fiscal Year": year,
                "Raw Data": f"FY{year} disclosed one-off evidence",
                "Calculation": f"FY {year} normalization adjustment = 25",
                "Explanation": f"Fiscal year {year} evidence was reviewed.",
                "One-Off Category": f"FY{year} restructuring",
                "Evidence Narrative": f"Evidence for {year}",
                "Value": 25.0,
                "Flag": year == 2024,
                "Severity": "Medium" if year == 2024 else "None",
                "Review Status": "Reviewed",
                "Source Date": f"{year}-11-01",
            }
            for year in (2022, 2023, 2024, 2025)
        ]
    )
    year_map = {2022: 2021, 2023: 2022, 2024: 2023, 2025: 2024}

    restored = _restore_normalization_fiscal_years(canonical, year_map)

    for canonical_year, actual_year in year_map.items():
        row = restored.loc[restored["Fiscal Year"].eq(actual_year)].iloc[0]
        for column in (
            "Raw Data", "Calculation", "Explanation", "One-Off Category",
            "Evidence Narrative",
        ):
            assert str(actual_year) in row[column]
            assert str(canonical_year) not in row[column]
    assert "FY2021" in restored.loc[
        restored["Fiscal Year"].eq(2021), "Raw Data"
    ].iloc[0]
    assert "FY2023" not in restored.loc[
        restored["Fiscal Year"].eq(2021), "Raw Data"
    ].iloc[0]
    pd.testing.assert_series_equal(restored["Value"], canonical["Value"])
    pd.testing.assert_series_equal(restored["Flag"], canonical["Flag"])
    pd.testing.assert_series_equal(restored["Severity"], canonical["Severity"])
    pd.testing.assert_series_equal(
        restored["Review Status"], canonical["Review Status"]
    )
    pd.testing.assert_series_equal(restored["Source Date"], canonical["Source Date"])


def test_fy2023_to_fy2026_normalization_red_flag_text_uses_actual_years():
    shifted_data = APPLE_BENCHMARK_DATA.copy(deep=True)
    shifted_data["Fiscal Year"] = shifted_data["Fiscal Year"] + 1
    shifted_one_offs = APPLE_ONE_OFF_FIXTURE.copy(deep=True)
    shifted_one_offs["Fiscal Year"] = shifted_one_offs["Fiscal Year"] + 1
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com",
        one_off_evidence=shifted_one_offs,
    )

    calculations = modules.run_calculations(shifted_data)
    red_flags = calculations["analysis_tables"]["red_flags"]
    latest_normalization = red_flags.loc[
        red_flags["Fiscal Year"].eq(2026)
        & red_flags["Metric"].isin(
            ("Large normalization difference", "Repeated one-off items")
        )
    ]

    assert len(latest_normalization) == 2
    repeated = latest_normalization.loc[
        latest_normalization["Metric"].eq("Repeated one-off items")
    ].iloc[0]
    assert "Categories identified in 2026" in repeated["Raw Data"]
    assert "Categories identified in 2025" not in repeated["Raw Data"]


def test_task_112_identity_year_mapping_leaves_2022_through_2025_unchanged():
    evidence = pd.DataFrame(
        [
            {
                "Fiscal Year": year,
                "Raw Data": f"FY{year} evidence",
                "Calculation": f"Calculation for {year}",
                "Explanation": f"FY {year} normalization status unchanged",
                "Value": float(year),
                "Flag": year == 2024,
                "Severity": "Medium" if year == 2024 else "None",
                "Review Status": "Reviewed",
            }
            for year in (2022, 2023, 2024, 2025)
        ]
    )

    restored = _restore_normalization_fiscal_years(
        evidence, {year: year for year in (2022, 2023, 2024, 2025)}
    )

    pd.testing.assert_frame_equal(restored, evidence)


def test_missing_data_keeps_unrelated_results_and_marks_dependencies_unavailable():
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )
    calculations = modules.run_calculations(
        partial_company_frame(inventory_2024=None)
    )
    analysis = modules.run_red_flags_and_severity(calculations)

    summary = calculations["financial_summary"].set_index("Fiscal Year")
    assert summary.loc[2024, "Revenue Growth"] == 0.1
    accrual = analysis["red_flags"].loc[
        (analysis["red_flags"]["Fiscal Year"] == 2024)
        & (analysis["red_flags"]["Metric"] == "AR growth vs Revenue growth")
    ].iloc[0]
    assert accrual["Result"] == "No Flag"

    working = analysis["working_capital"].set_index("Fiscal Year")
    assert working.loc[2024, "Inventory Result"] == "Unavailable"
    assert working.loc[2024, "WC Result"] == "Unavailable"
    assert working.loc[2024, "AP Result"] == "No Flag"
    assert "Inventory (FY 2024)" in working.loc[2024, "Missing Evidence"]

    unavailable = calculations["unavailable_outputs"]
    affected = unavailable.loc[
        (unavailable["Analysis"] == "Working Capital")
        & (unavailable["Fiscal Year"] == 2024)
    ]
    assert set(affected["Status"]) == {"Unavailable"}
    assert set(affected["Missing Metric"]) == {"Inventory"}
    assert set(affected["Missing Fiscal Year"]) == {2024}


def test_missing_da_keeps_da_and_capex_to_da_outputs_unavailable():
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )
    calculations = modules.run_calculations(
        partial_company_frame(inventory_2024=84.0, da_2024=None)
    )

    summary = calculations["financial_summary"].set_index("Fiscal Year")
    assert pd.isna(summary.loc[2024, "Depreciation & Amortization"])
    assert pd.isna(summary.loc[2024, "D&A Growth"])
    assert pd.isna(summary.loc[2024, "D&A / Revenue"])
    assert pd.isna(summary.loc[2024, "CapEx / D&A"])
    assert pd.isna(summary.loc[2025, "D&A Growth"])

    unavailable = calculations["unavailable_outputs"]
    affected = unavailable.loc[
        unavailable["Missing Metric"].eq("Depreciation & Amortization")
        & unavailable["Fiscal Year"].eq(2024)
    ]
    assert {"D&A Growth", "D&A / Revenue", "CapEx / D&A"}.issubset(
        set(affected["Output"])
    )
    assert set(affected["Status"]) == {"Unavailable"}
    following_growth = unavailable.loc[
        unavailable["Missing Metric"].eq("Depreciation & Amortization")
        & unavailable["Fiscal Year"].eq(2025)
        & unavailable["Output"].eq("D&A Growth")
    ]
    assert len(following_growth) == 1
    assert following_growth.iloc[0]["Missing Fiscal Year"] == 2024


def test_missing_evidence_never_becomes_a_false_clean_result():
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )
    calculations = modules.run_calculations(
        partial_company_frame(inventory_2024=None)
    )
    analysis = modules.run_red_flags_and_severity(calculations)

    inventory_rules = analysis["red_flags"].loc[
        analysis["red_flags"]["Metric"].eq(
            "Inventory growth vs Revenue growth"
        )
        & analysis["red_flags"]["Fiscal Year"].isin((2024, 2025))
    ]
    assert set(inventory_rules["Result"]) == {"Unavailable"}
    assert set(inventory_rules["Severity"]) == {"Unavailable"}
    assert not inventory_rules["Result"].isin(("No Flag", "Low Risk")).any()
    assert analysis["overall_severity"].iloc[0]["Availability"] == "Partial"


def test_partial_analysis_warning_identifies_missing_data_and_correction_path():
    app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
    main_source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
    assert "st.warning(result.partial_notice)" in app_source
    assert "Partial analysis: validated available data was analyzed" in main_source
    assert "dependent outputs are Unavailable" in main_source
    assert "Correct Extracted Data panel" in main_source
    assert "Missing Fiscal Year" in main_source


def test_manual_correction_restores_affected_analysis():
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )
    frame = partial_company_frame(inventory_2024=None)
    mask = frame["Metric"].eq("Inventory") & frame["Fiscal Year"].eq(2024)
    missing_record = frame.loc[mask].iloc[0].to_dict()
    missing_record.update(
        {
            "raw_sec_value": missing_record["Value"],
            "raw_unit": missing_record["Units"],
            "status": "MISSING",
        }
    )
    correction = create_manual_correction(
        missing_record,
        84.0,
        "Verified against the reviewed annual filing",
        corrected_unit="USD millions",
    )
    corrected = _apply_correction_overlay(frame, (correction,))
    assert corrected.loc[mask, "Original Value"].isna().all()
    assert corrected.loc[mask, "Value"].iloc[0] == effective_value(
        missing_record, correction
    )

    calculations = modules.run_calculations(corrected)
    analysis = modules.run_red_flags_and_severity(calculations)
    working = analysis["working_capital"].set_index("Fiscal Year")

    assert working.loc[2024, "Inventory Result"] != "Unavailable"
    assert working.loc[2024, "WC Result"] != "Unavailable"
    assert not calculations["unavailable_outputs"]["Missing Metric"].eq(
        "Inventory"
    ).any()


def test_partial_interpretation_cannot_return_a_false_clean_conclusion():
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )
    corrected = partial_company_frame(inventory_2024=None)
    calculations = modules.run_calculations(corrected)
    analysis = modules.run_red_flags_and_severity(calculations)
    validation = gate(can_analyze=False)
    company = SimpleNamespace(
        company_name="Partial Data Industries", ticker="PART"
    )

    structured = modules.build_structured_ai_input(
        company, validation, corrected, calculations, analysis
    )
    interpretations = modules.run_interpretations(structured)

    assert structured["partial_analysis"]["status"] == "Partial"
    assert interpretations["final_conclusion"][
        "earnings_quality_conclusion"
    ] == "Needs Investigation"
    final = interpretations["final_conclusion"]
    assert final["analysis_status"] == "Partial Analysis"
    assert "Partial Analysis" in final["explanation"]
    assert "Inventory (FY 2024)" in final["explanation"]
    assert "remain Unavailable" in final["explanation"]
    assert "not treated as No Flag, Low Risk, zero" in final["explanation"]
    assert "may change" in final["explanation"]
    assert "correction panel" in final["explanation"]


def test_complete_data_final_conclusion_is_unchanged():
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )
    corrected = partial_company_frame(inventory_2024=84.0)
    calculations = modules.run_calculations(corrected)
    analysis = modules.run_red_flags_and_severity(calculations)
    company = SimpleNamespace(
        company_name="Partial Data Industries", ticker="PART"
    )

    structured = modules.build_structured_ai_input(
        company, gate(can_analyze=True), corrected, calculations, analysis
    )
    interpretations = modules.run_interpretations(structured)

    assert "partial_analysis" not in structured
    assert interpretations["final_conclusion"][
        "earnings_quality_conclusion"
    ] == "Needs Investigation"
    assert "analysis_status" not in interpretations["final_conclusion"]


def test_production_calculations_support_five_annual_periods():
    base_records = []
    values = {
        "Revenue": [900.0, 1_000.0, 1_100.0, 1_210.0, 1_331.0],
        "Net Income": [90.0, 100.0, 110.0, 121.0, 133.1],
        "Operating Cash Flow": [135.0, 150.0, 165.0, 181.5, 199.65],
        "Accounts Receivable": [95.0, 100.0, 105.0, 110.0, 115.0],
        "Inventory": [78.0, 80.0, 82.0, 84.0, 86.0],
        "Accounts Payable": [65.0, 70.0, 75.0, 80.0, 85.0],
        "Depreciation & Amortization": [38.0, 40.0, 42.0, 44.0, 46.0],
        "Capital Expenditures": [48.0, 50.0, 52.0, 54.0, 56.0],
        "Stock-Based Compensation": [4.5, 5.0, 5.5, 6.0, 6.5],
        "Shares Outstanding": [99.5, 100.0, 100.5, 101.0, 101.5],
        "Deferred Tax Assets": [19.0, 20.0, 21.0, 22.0, 23.0],
        "Deferred Tax Liabilities": [9.0, 10.0, 11.0, 12.0, 13.0],
        "Tax Expense": [18.0, 20.0, 22.0, 24.0, 26.0],
    }
    for position, fiscal_year in enumerate((2021, 2022, 2023, 2024, 2025)):
        for metric, annual_values in values.items():
            base_records.append({
                "Company": "Five Year Industries",
                "Ticker": "FIVE",
                "Fiscal Year": fiscal_year,
                "Metric": metric,
                "Value": annual_values[position],
                "Units": "shares millions" if metric == "Shares Outstanding" else "USD millions",
                "Financial Statement": "Reviewed test fixture",
                "Source": "https://www.sec.gov/Archives/five-year",
                "Source Date": "2026-01-01",
            })
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )

    calculations = modules.run_calculations(pd.DataFrame(base_records))
    analysis = modules.run_red_flags_and_severity(calculations)

    assert calculations["financial_summary"]["Fiscal Year"].tolist() == [
        2021, 2022, 2023, 2024, 2025
    ]
    assert calculations["financial_summary"].set_index("Fiscal Year").loc[
        2025, "Revenue"
    ] == 1_331.0
    assert analysis["red_flags"]["Fiscal Year"].nunique() == 4
    assert analysis["fiscal_year_severity"]["Fiscal Year"].tolist() == [
        2022, 2023, 2024, 2025
    ]


def test_rolling_production_analysis_supports_4_5_7_and_10_years():
    all_years = tuple(range(2016, 2026))
    starting_values = {
        "Revenue": 1_000.0,
        "Net Income": 100.0,
        "Operating Cash Flow": 150.0,
        "Accounts Receivable": 100.0,
        "Inventory": 80.0,
        "Accounts Payable": 70.0,
        "Depreciation & Amortization": 40.0,
        "Capital Expenditures": 50.0,
        "Stock-Based Compensation": 5.0,
        "Shares Outstanding": 100.0,
        "Deferred Tax Assets": 20.0,
        "Deferred Tax Liabilities": 10.0,
        "Tax Expense": 20.0,
    }
    records = []
    for position, fiscal_year in enumerate(all_years):
        for metric, starting_value in starting_values.items():
            records.append({
                "Company": "Long History Industries",
                "Ticker": "LONG",
                "Fiscal Year": fiscal_year,
                "Metric": metric,
                "Value": starting_value * (1.05 ** position),
                "Units": "shares millions" if metric == "Shares Outstanding" else "USD millions",
                "Financial Statement": "Reviewed test fixture",
                "Source": "https://www.sec.gov/Archives/long-history",
                "Source Date": "2026-01-01",
            })
    full_frame = pd.DataFrame(records)
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )

    for year_count in (4, 5, 7, 10):
        selected_years = all_years[-year_count:]
        selected_frame = full_frame.loc[
            full_frame["Fiscal Year"].isin(selected_years)
        ].copy()
        calculations = modules.run_calculations(selected_frame)
        analysis = modules.run_red_flags_and_severity(calculations)

        assert calculations["financial_summary"]["Fiscal Year"].tolist() == list(
            selected_years
        )
        assert not calculations["financial_summary"]["Fiscal Year"].duplicated().any()
        assert analysis["red_flags"]["Fiscal Year"].tolist() == sorted(
            analysis["red_flags"]["Fiscal Year"].tolist()
        )
        assert not analysis["red_flags"].duplicated(
            subset=["Fiscal Year", "Metric"]
        ).any()
        assert analysis["fiscal_year_severity"]["Fiscal Year"].tolist() == list(
            selected_years[1:]
        )


def test_production_validation_blocks_fewer_than_four_annual_years():
    values = tuple(
        SimpleNamespace(
            fiscal_year=year,
            financial_field="Revenue",
            raw_value=100.0,
            unit="USD millions",
            financial_statement="Income Statement",
            source_url="https://www.sec.gov/Archives/short-history",
            filing_date="2026-01-01",
            status="RETRIEVED",
            period_start=f"{year - 1}-01-01",
            period_end=f"{year}-01-01",
            filing_form="10-K",
            accession_number=f"short-{year}",
            sec_source_identifier=f"short-{year}",
            xbrl_taxonomy="us-gaap",
            xbrl_concept="Revenues",
            missing_reason=None,
            validation_reason=None,
        )
        for year in (2023, 2024, 2025)
    )
    statements = SimpleNamespace(
        company_name="Short History Industries",
        ticker="SHRT",
        values=values,
    )
    modules = create_production_pipeline_modules(
        user_agent="EarningsQualityAgent tests@example.com"
    )

    validation = modules.validate_data(statements, 4, ())

    assert validation.decision is AnalysisDecision.STOP
    assert validation.can_analyze is False
    assert validation.blocking_issue_count == 1
    assert "At least four usable SEC annual fiscal years are required" in (
        validation.blocking_issues[0].explanation
    )


if __name__ == "__main__":
    test_pipeline_executes_existing_modules_in_required_order_and_passes_outputs()
    test_missing_validation_continues_downstream_analysis()
    test_production_factory_configures_every_real_pipeline_stage()
    test_company_selector_options_come_from_official_sec_data_and_include_ups()
    test_non_apple_dataset_feeds_production_calculations_and_red_flags()
    test_missing_data_keeps_unrelated_results_and_marks_dependencies_unavailable()
    test_missing_evidence_never_becomes_a_false_clean_result()
    test_partial_analysis_warning_identifies_missing_data_and_correction_path()
    test_manual_correction_restores_affected_analysis()
    test_production_calculations_support_five_annual_periods()
    test_rolling_production_analysis_supports_4_5_7_and_10_years()
    test_production_validation_blocks_fewer_than_four_annual_years()
    print("Task 109 pipeline controller tests passed")
