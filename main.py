"""Task 109 pipeline controller for the earnings-quality analyzer.

The controller deliberately contains no financial calculations, thresholds,
classification rules, interpretation text, or workbook construction logic.
Those responsibilities remain in the existing project modules supplied through
``PipelineModules``.
"""

from __future__ import annotations

import contextlib
import ast
import importlib
import io
import os
import re
import sys
import types
from zipfile import BadZipFile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Tuple

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from Data.analysis_validation_gate import (
    AnalysisDecision,
    AnalysisValidationGateResult,
    BlockingIssue,
    evaluate_integrated_annual_dataset,
)
from Data.company_identifier import (
    CompanyIdentity,
    IdentificationStatus,
    identify_company,
)
from Data.financial_statement_fetcher import SECFinancialStatementFetcher


PIPELINE_STAGES = (
    "Data extraction",
    "Validation",
    "Calculations",
    "Red flags",
    "AI interpretation",
    "Excel generation",
)
ProgressCallback = Callable[[str, str], None]


@dataclass(frozen=True)
class SupportedCompany:
    """One company approved for display in the main application selector."""

    category: str
    company_name: str
    ticker: str


SUPPORTED_COMPANIES: Tuple[SupportedCompany, ...] = (
    SupportedCompany("Technology", "Apple Inc.", "AAPL"),
    SupportedCompany("Technology", "Microsoft Corporation", "MSFT"),
    SupportedCompany("Technology", "NVIDIA Corporation", "NVDA"),
    SupportedCompany("Technology", "Alphabet Inc.", "GOOGL"),
    SupportedCompany("Technology", "Meta Platforms, Inc.", "META"),
    SupportedCompany("Technology", "Adobe Inc.", "ADBE"),
    SupportedCompany("Technology", "Salesforce, Inc.", "CRM"),
    SupportedCompany("Technology", "Intel Corporation", "INTC"),
    SupportedCompany("Technology", "Advanced Micro Devices, Inc.", "AMD"),
    SupportedCompany("Technology", "Cisco Systems, Inc.", "CSCO"),
    SupportedCompany("Consumer / Retail", "Amazon.com, Inc.", "AMZN"),
    SupportedCompany("Consumer / Retail", "Walmart Inc.", "WMT"),
    SupportedCompany("Consumer / Retail", "Costco Wholesale Corporation", "COST"),
    SupportedCompany("Consumer / Retail", "The Home Depot, Inc.", "HD"),
    SupportedCompany("Consumer / Retail", "NIKE, Inc.", "NKE"),
    SupportedCompany("Consumer / Retail", "Starbucks Corporation", "SBUX"),
    SupportedCompany("Consumer / Retail", "McDonald's Corporation", "MCD"),
    SupportedCompany("Consumer / Retail", "The Coca-Cola Company", "KO"),
    SupportedCompany("Consumer / Retail", "PepsiCo, Inc.", "PEP"),
    SupportedCompany("Consumer / Retail", "Procter & Gamble Co.", "PG"),
    SupportedCompany("Industrial / Transportation", "Caterpillar Inc.", "CAT"),
    SupportedCompany("Industrial / Transportation", "Deere & Company", "DE"),
    SupportedCompany("Industrial / Transportation", "Honeywell International Inc.", "HON"),
    SupportedCompany("Industrial / Transportation", "3M Company", "MMM"),
    SupportedCompany("Industrial / Transportation", "United Parcel Service, Inc.", "UPS"),
    SupportedCompany("Industrial / Transportation", "FedEx Corporation", "FDX"),
    SupportedCompany("Industrial / Transportation", "Union Pacific Corporation", "UNP"),
    SupportedCompany("Industrial / Transportation", "General Electric Company", "GE"),
    SupportedCompany("Industrial / Transportation", "RTX Corporation", "RTX"),
    SupportedCompany("Industrial / Transportation", "Lockheed Martin Corporation", "LMT"),
    SupportedCompany("Automotive / Energy", "Tesla, Inc.", "TSLA"),
    SupportedCompany("Automotive / Energy", "General Motors Company", "GM"),
    SupportedCompany("Automotive / Energy", "Ford Motor Company", "F"),
    SupportedCompany("Automotive / Energy", "Exxon Mobil Corporation", "XOM"),
    SupportedCompany("Automotive / Energy", "Chevron Corporation", "CVX"),
    SupportedCompany("Automotive / Energy", "ConocoPhillips", "COP"),
    SupportedCompany("Healthcare / Pharmaceuticals", "Johnson & Johnson", "JNJ"),
    SupportedCompany("Healthcare / Pharmaceuticals", "Pfizer Inc.", "PFE"),
    SupportedCompany("Healthcare / Pharmaceuticals", "Merck & Co., Inc.", "MRK"),
    SupportedCompany("Healthcare / Pharmaceuticals", "Eli Lilly and Company", "LLY"),
    SupportedCompany("Healthcare / Pharmaceuticals", "AbbVie Inc.", "ABBV"),
    SupportedCompany("Telecommunications / Media", "Verizon Communications Inc.", "VZ"),
    SupportedCompany("Telecommunications / Media", "AT&T Inc.", "T"),
    SupportedCompany("Telecommunications / Media", "The Walt Disney Company", "DIS"),
    SupportedCompany("Telecommunications / Media", "Netflix, Inc.", "NFLX"),
    SupportedCompany("Telecommunications / Media", "Comcast Corporation", "CMCSA"),
)


class PipelineStageError(RuntimeError):
    """A pipeline failure annotated with its exact Task 110 stage."""

    def __init__(self, failed_stage: str, original_error: Exception) -> None:
        self.failed_stage = failed_stage
        self.original_error = original_error
        self.original_message = str(original_error)
        super().__init__(f"{failed_stage} failed: {self.original_message}")


@dataclass(frozen=True)
class PipelineModules:
    """Existing module entry points used by the controller, in pipeline order."""

    identify_company: Callable[[str], Any]
    extract_data: Callable[[Any, int], Any]
    validate_data: Callable[
        [Any, int, Tuple[Any, ...]], AnalysisValidationGateResult
    ]
    apply_manual_corrections: Callable[[Any, Tuple[Any, ...]], Any]
    run_calculations: Callable[[Any], Any]
    run_red_flags_and_severity: Callable[[Any], Any]
    build_structured_ai_input: Callable[
        [Any, AnalysisValidationGateResult, Any, Any, Any], Any
    ]
    run_interpretations: Callable[[Any], Any]
    generate_excel: Callable[[Any, Any, Any, Any, Any, Any, Any], Any]


@dataclass(frozen=True)
class PipelineResult:
    """Outputs returned by one controller run.

    A blocked result contains identification, extraction, and validation only.
    Downstream fields stay missing because their modules were never called.
    """

    company: Any
    extracted_data: Any
    validation: AnalysisValidationGateResult
    corrected_data: Any = None
    calculations: Any = None
    red_flags_and_severity: Any = None
    structured_ai_input: Any = None
    interpretations: Any = None
    excel_output: Any = None

    @property
    def blocked(self) -> bool:
        return (
            self.calculations is None
            and (
                not self.validation.can_analyze
                or self.validation.decision is AnalysisDecision.STOP
            )
        )

    @property
    def partial(self) -> bool:
        """Whether analysis continued with explicitly unavailable evidence."""

        return bool(self.validation.blocking_issues) and not self.blocked

    @property
    def partial_notice(self) -> Optional[str]:
        """Compact user-facing notice with exact unavailable evidence."""

        if not self.partial:
            return None
        missing_items = sorted(
            {
                (issue.metric, int(issue.fiscal_year))
                for issue in self.validation.blocking_issues
            },
            key=lambda item: (item[1], item[0]),
        )
        missing = ", ".join(
            f"{metric} (FY {fiscal_year})"
            for metric, fiscal_year in missing_items[:5]
        )
        if len(missing_items) > 5:
            missing += f", plus {len(missing_items) - 5} more missing item(s)"
        return (
            "Partial analysis: validated available data was analyzed, but "
            f"dependent outputs are Unavailable because of {missing}. Add "
            "verified values through the Correct Extracted Data panel and rerun."
        )


def _requires_hard_stop(validation: AnalysisValidationGateResult) -> bool:
    """Retain STOP only for structural conditions that prevent any analysis."""

    return any(
        issue.blocking_status == "INSUFFICIENT_ANNUAL_HISTORY"
        for issue in validation.blocking_issues
    )


def _mask_unvalidated_values(
    corrected_data: Any, validation: AnalysisValidationGateResult
) -> Any:
    """Keep invalid facts missing before calculations; never substitute a value."""

    if not isinstance(corrected_data, pd.DataFrame):
        return corrected_data
    result = corrected_data.copy(deep=True)
    if not {"Metric", "Fiscal Year", "Value"}.issubset(result.columns):
        return result
    for issue in validation.blocking_issues:
        mask = result["Metric"].eq(issue.metric) & result["Fiscal Year"].eq(
            issue.fiscal_year
        )
        if mask.any():
            result.loc[mask, "Value"] = None
    return result


def _apply_correction_overlay(
    frame: pd.DataFrame, corrections: Tuple[Any, ...]
) -> pd.DataFrame:
    """Apply active correction values while preserving original extracted data."""

    result = frame.copy(deep=True)
    correction_index = {
        (item.metric, int(item.fiscal_year)): item for item in corrections
    }
    result.insert(
        result.columns.get_loc("Value") + 1,
        "Original Value",
        result["Value"],
    )
    result["Value"] = [
        (
            correction.effective_value
            if correction is not None
            else row["Value"]
        )
        for row in result.to_dict("records")
        for correction in (
            correction_index.get((row["Metric"], int(row["Fiscal Year"]))),
        )
    ]
    result["Correction Status"] = [
        correction.correction_status.value if correction is not None else None
        for row in result.to_dict("records")
        for correction in (
            correction_index.get((row["Metric"], int(row["Fiscal Year"]))),
        )
    ]
    result["Correction Reason"] = [
        correction.correction_reason if correction is not None else None
        for row in result.to_dict("records")
        for correction in (
            correction_index.get((row["Metric"], int(row["Fiscal Year"]))),
        )
    ]
    result["Correction Entered Value"] = [
        correction.corrected_value if correction is not None else None
        for row in result.to_dict("records")
        for correction in (
            correction_index.get((row["Metric"], int(row["Fiscal Year"]))),
        )
    ]
    return result


def _selected_fiscal_years(values: Iterable[Any]) -> Tuple[int, ...]:
    return tuple(sorted({int(value) for value in values}))


def _final_workbook_path(company: Any, fiscal_years: Iterable[Any]) -> Path:
    safe_ticker = "".join(
        character for character in str(company.ticker).upper()
        if character.isalnum() or character in {"-", "_"}
    )
    years = _selected_fiscal_years(fiscal_years)
    if not safe_ticker:
        raise ValueError("A valid company ticker is required for Excel generation")
    if not years:
        raise ValueError("Fiscal years are required for Excel generation")
    year_token = "_".join(str(year) for year in years)
    return (
        _PROJECT_ROOT / "excel reports"
        / f"earnings_quality_analysis_{safe_ticker}_{year_token}.xlsx"
    )


def pipeline_result_matches_selection(
    result: Any, company: Any, fiscal_years: Iterable[Any]
) -> bool:
    """Confirm that a result belongs to the company and years visible in the UI."""

    if result is None or company is None:
        return False
    result_company = getattr(result, "company", None)
    validation = getattr(result, "validation", None)
    try:
        result_years = _selected_fiscal_years(
            validation.requested_fiscal_years
        )
        expected_years = _selected_fiscal_years(fiscal_years)
    except (AttributeError, TypeError, ValueError):
        return False
    return (
        str(getattr(result_company, "ticker", "")).casefold()
        == str(getattr(company, "ticker", "")).casefold()
        and result_years == expected_years
    )


def downloadable_workbook_path(
    result: Any, company: Any, fiscal_years: Iterable[Any]
) -> Optional[Path]:
    """Return only a valid workbook matching the current UI selection."""

    if not pipeline_result_matches_selection(result, company, fiscal_years):
        return None
    output = getattr(result, "excel_output", None)
    if not output:
        return None
    path = Path(output)
    try:
        result_company = result.company
        result_years = _selected_fiscal_years(
            result.validation.requested_fiscal_years
        )
        expected_path = _final_workbook_path(result_company, result_years)
        if path.resolve() != expected_path.resolve():
            return None
        if path.suffix.casefold() != ".xlsx" or not path.is_file():
            return None
        if path.stat().st_size == 0:
            return None
        workbook = load_workbook(path, read_only=True, data_only=False)
        try:
            expected_year_text = ", ".join(
                str(year) for year in result_years
            )
            matches = (
                "Dashboard" in workbook.sheetnames
                and workbook["Dashboard"]["A2"].value
                == f"{result_company.company_name} ({result_company.ticker})"
                and workbook["Dashboard"]["A8"].value == expected_year_text
            )
        finally:
            workbook.close()
        return path if matches else None
    except (
        BadZipFile,
        InvalidFileException,
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ):
        return None


class EarningsQualityController:
    """Run existing project modules as one ordered pipeline."""

    def __init__(self, modules: PipelineModules) -> None:
        if not isinstance(modules, PipelineModules):
            raise TypeError("modules must be a PipelineModules instance")
        self._modules = modules

    def run(
        self,
        company_or_ticker: str,
        number_of_fiscal_years: int,
        *,
        manual_corrections: Iterable[Any] = (),
        progress_callback: Optional[ProgressCallback] = None,
    ) -> PipelineResult:
        """Execute the pipeline, preserving unavailable evidence as missing."""

        if not isinstance(company_or_ticker, str) or not company_or_ticker.strip():
            raise ValueError("company_or_ticker is required")
        if (
            isinstance(number_of_fiscal_years, bool)
            or not isinstance(number_of_fiscal_years, int)
            or not 4 <= number_of_fiscal_years <= 10
        ):
            raise ValueError("number_of_fiscal_years must be between 4 and 10")

        def report(stage: str, status: str) -> None:
            if progress_callback is not None:
                progress_callback(stage, status)

        @contextlib.contextmanager
        def stage(stage_name: str):
            report(stage_name, "started")
            try:
                yield
            except Exception as error:
                raise PipelineStageError(stage_name, error) from error
            else:
                report(stage_name, "completed")

        corrections = tuple(manual_corrections)
        with stage("Data extraction"):
            company = self._modules.identify_company(company_or_ticker)
            extracted_data = self._modules.extract_data(
                company, number_of_fiscal_years
            )

        with stage("Validation"):
            validation = self._modules.validate_data(
                extracted_data, number_of_fiscal_years, corrections
            )
            if not isinstance(validation, AnalysisValidationGateResult) and not all(
                hasattr(validation, attribute)
                for attribute in (
                    "decision", "can_analyze", "requested_fiscal_years",
                    "blocking_issues", "metric_year_results", "blocking_issue_count",
                )
            ):
                raise TypeError(
                    "validate_data must return an AnalysisValidationGateResult"
                )
            hard_stop = _requires_hard_stop(validation)

        # Insufficient annual history prevents the four-period analysis. Missing
        # or invalid individual facts instead produce a partial analysis in which
        # only their dependent outputs are explicitly unavailable.
        if hard_stop:
            return PipelineResult(
                company=company,
                extracted_data=extracted_data,
                validation=validation,
            )

        with stage("Calculations"):
            corrected_data = self._modules.apply_manual_corrections(
                extracted_data, corrections
            )
            corrected_data = _mask_unvalidated_values(corrected_data, validation)
            calculations = self._modules.run_calculations(corrected_data)

        with stage("Red flags"):
            red_flags_and_severity = self._modules.run_red_flags_and_severity(
                calculations
            )

        with stage("AI interpretation"):
            structured_ai_input = self._modules.build_structured_ai_input(
                company,
                validation,
                corrected_data,
                calculations,
                red_flags_and_severity,
            )
            interpretations = self._modules.run_interpretations(
                structured_ai_input
            )

        with stage("Excel generation"):
            excel_output = self._modules.generate_excel(
                company,
                corrected_data,
                calculations,
                red_flags_and_severity,
                structured_ai_input,
                interpretations,
                validation,
            )

        return PipelineResult(
            company=company,
            extracted_data=extracted_data,
            validation=validation,
            corrected_data=corrected_data,
            calculations=calculations,
            red_flags_and_severity=red_flags_and_severity,
            structured_ai_input=structured_ai_input,
            interpretations=interpretations,
            excel_output=excel_output,
        )


def _sec_fetcher(
    user_agent: Optional[str],
    fetcher: Optional[SECFinancialStatementFetcher] = None,
) -> SECFinancialStatementFetcher:
    if fetcher is not None:
        return fetcher
    configured_user_agent = user_agent or os.environ.get("SEC_USER_AGENT")
    if not configured_user_agent:
        raise ValueError("SEC_USER_AGENT is required for official SEC extraction")
    return SECFinancialStatementFetcher(configured_user_agent)


def sec_company_options(
    *,
    user_agent: Optional[str] = None,
    fetcher: Optional[SECFinancialStatementFetcher] = None,
) -> Tuple[CompanyIdentity, ...]:
    """Return SEC-resolvable companies from the curated selector allowlist."""

    client = _sec_fetcher(user_agent, fetcher)
    official_tickers = {record.ticker for record in client.list_companies()}
    return tuple(
        CompanyIdentity(
            company_name=company.company_name,
            ticker=company.ticker,
            country="United States",
            regulator="SEC",
        )
        for company in SUPPORTED_COMPANIES
        if company.ticker in official_tickers
    )


def search_supported_company_options(
    query: str, options: Iterable[CompanyIdentity]
) -> Tuple[CompanyIdentity, ...]:
    """Match active curated options by a company-name or ticker substring."""

    normalized_query = str(query).strip().casefold()
    active_options = tuple(options)
    if not normalized_query:
        return active_options
    return tuple(
        company
        for company in active_options
        if normalized_query in company.company_name.casefold()
        or normalized_query in company.ticker.casefold()
    )


def identify_official_company(
    company_or_ticker: str,
    *,
    user_agent: Optional[str] = None,
    fetcher: Optional[SECFinancialStatementFetcher] = None,
) -> CompanyIdentity:
    """Resolve and verify a company through the official SEC company universe."""

    local_result = identify_company(company_or_ticker)
    lookup: Any = company_or_ticker
    if (
        local_result.status is IdentificationStatus.MATCHED
        and local_result.company is not None
    ):
        lookup = local_result.company
    client = _sec_fetcher(user_agent, fetcher)
    record = client.resolve_cik(lookup)
    return CompanyIdentity(
        company_name=record.company_name,
        ticker=record.ticker,
        country="United States",
        regulator="SEC",
    )


def available_fiscal_years(
    company_or_ticker: str,
    *,
    user_agent: Optional[str] = None,
    fetcher: Optional[SECFinancialStatementFetcher] = None,
) -> Tuple[int, ...]:
    """Return up to ten usable annual SEC filing years for selection."""

    client = _sec_fetcher(user_agent, fetcher)
    company = identify_official_company(company_or_ticker, fetcher=client)
    statements = client.fetch(company)
    years = sorted(
        {
            int(value.fiscal_year)
            for value in statements.values
            if value.raw_value is not None
        }
    )
    return tuple(years[-10:])


def _financial_statements_frame(statements: Any) -> pd.DataFrame:
    """Expose extracted SEC facts to validation without changing their values."""

    rows = []
    for value in statements.values:
        is_duration = value.period_start is not None
        rows.append(
            {
                "Company": statements.company_name,
                "Ticker": statements.ticker,
                "Fiscal Year": value.fiscal_year,
                "Metric": value.financial_field,
                "Value": value.raw_value,
                "Units": value.unit,
                "Raw Unit": value.unit,
                "Financial Statement": value.financial_statement,
                "Source": value.source_url,
                "Source Date": value.filing_date,
                "Status": value.status,
                "Period Start": value.period_start,
                "Period End": value.period_end,
                "Balance Sheet Date": None if is_duration else value.period_end,
                "Filing Form": value.filing_form,
                "Accession Number": value.accession_number,
                "SEC Source Identifier": value.sec_source_identifier,
                "XBRL Taxonomy": value.xbrl_taxonomy,
                "XBRL Concept": value.xbrl_concept,
                "Missing Reason": value.missing_reason,
                "Validation Reason": value.validation_reason,
            }
        )
    return pd.DataFrame(rows)


_PROJECT_ROOT = Path(__file__).resolve().parent
_CANONICAL_YEARS = (2022, 2023, 2024, 2025)
_ONE_OFF_REQUIRED_FIELDS = (
    "Company", "Ticker", "Fiscal Year", "Category", "Description", "Value",
    "Units", "Direction", "Tax Basis", "Availability", "Source",
    "Source Date", "Source Detail",
)
_ONE_OFF_CLASSIFICATION_FIELDS = (
    "Manual Classification", "Manual Review Status",
)
_ONE_OFF_CATEGORIES = (
    "Asset-sale gains", "Restructuring", "Legal settlements", "Impairments",
    "Acquisition-related charges", "Unusual tax gains/losses",
    "Other unusual items",
)
_DYNAMIC_ANALYSIS_MODULES = (
    "Calculations.revenue_growth", "Calculations.net_income_growth",
    "Calculations.ocf_growth", "Calculations.ar_growth",
    "Calculations.accrual_cash_comparison", "Calculations.da_analysis",
    "Calculations.capex_analysis", "Calculations.free_cash_flow",
    "Calculations.working_capital_movements",
    "Calculations.working_capital_analysis", "Calculations.sbc_analysis",
    "Calculations.share_dilution", "Calculations.normalized_net_income",
    "Analysis.inventory_warning", "Analysis.ap_warning",
    "Analysis.accrual_red_flags", "Analysis.capex_rule",
    "Analysis.manual_one_off_classification",
    "Analysis.repeated_one_off_detection",
    "Analysis.reported_vs_normalized_earnings",
    "Analysis.normalization_red_flags", "Analysis.dta_analysis",
    "Analysis.dtl_analysis", "Analysis.tax_red_flags",
    "Analysis.sbc_vs_dilution", "Analysis.buyback_adjustment",
    "Analysis.sbc_red_flags", "Analysis.working_capital_red_flags",
    "Analysis.red_flag_table", "Analysis.severity_system",
    "Analysis.master_analysis_table", "Analysis.excel_export",
)


def _module_prefix(module_name: str, stop_assignment: str) -> types.ModuleType:
    """Load a legacy module up to its benchmark-only self-test section."""

    path = _PROJECT_ROOT.joinpath(*module_name.split(".")).with_suffix(".py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    body = []
    for statement in tree.body:
        if (
            isinstance(statement, (ast.Assign, ast.AnnAssign))
            and any(
                isinstance(target, ast.Name) and target.id == stop_assignment
                for target in (
                    statement.targets
                    if isinstance(statement, ast.Assign)
                    else (statement.target,)
                )
            )
        ):
            break
        body.append(statement)
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    module.__package__ = module_name.rpartition(".")[0]
    sys.modules[module_name] = module
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), module.__dict__)
    return module


def _unavailable_one_offs(company_frame: pd.DataFrame) -> pd.DataFrame:
    company = company_frame.iloc[0]["Company"]
    ticker = company_frame.iloc[0]["Ticker"]
    rows = [
        {
            "Company": company, "Ticker": ticker, "Fiscal Year": year,
            "Category": "Unavailable", "Description": "Unavailable",
            "Value": float("nan"), "Units": "Not Available",
            "Direction": "Not Available", "Tax Basis": "Not Available",
            "Availability": "Not Available", "Source": "Not Available",
            "Source Date": "Not Available", "Source Detail": "Not Available",
        }
        for year in _CANONICAL_YEARS
    ]
    return pd.DataFrame(rows, columns=_ONE_OFF_REQUIRED_FIELDS)


def _validated_one_off_evidence(
    corrected_data: pd.DataFrame,
    one_off_evidence: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    """Validate explicitly supplied, manually reviewed one-off evidence."""

    if one_off_evidence is None:
        return None
    if not isinstance(one_off_evidence, pd.DataFrame) or one_off_evidence.empty:
        raise ValueError("Explicit one-off evidence must be a non-empty DataFrame")

    required = set(_ONE_OFF_REQUIRED_FIELDS + _ONE_OFF_CLASSIFICATION_FIELDS)
    missing = required.difference(one_off_evidence.columns)
    if missing:
        raise ValueError(
            "Explicit one-off evidence is missing required fields: "
            + ", ".join(sorted(missing))
        )

    evidence = one_off_evidence.loc[:, list(
        _ONE_OFF_REQUIRED_FIELDS + _ONE_OFF_CLASSIFICATION_FIELDS
    )].copy(deep=True)
    expected_companies = {
        str(value).casefold() for value in corrected_data["Company"].dropna().unique()
    }
    expected_tickers = {
        str(value).casefold() for value in corrected_data["Ticker"].dropna().unique()
    }
    evidence_companies = {
        str(value).casefold() for value in evidence["Company"].dropna().unique()
    }
    evidence_tickers = {
        str(value).casefold() for value in evidence["Ticker"].dropna().unique()
    }
    if evidence_companies != expected_companies or evidence_tickers != expected_tickers:
        raise ValueError("Explicit one-off evidence does not match the supplied company")

    expected_years = {
        int(value) for value in corrected_data["Fiscal Year"].dropna().unique()
    }
    evidence_years = {
        int(value) for value in evidence["Fiscal Year"].dropna().unique()
    }
    if evidence_years != expected_years:
        raise ValueError(
            "Explicit one-off evidence must match every supplied fiscal year exactly"
        )
    evidence["Fiscal Year"] = evidence["Fiscal Year"].astype(int)

    allowed_availability = {"Available", "Not Available"}
    if not set(evidence["Availability"]).issubset(allowed_availability):
        raise ValueError("Explicit one-off evidence has invalid Availability values")
    available = evidence["Availability"].eq("Available")
    if evidence.loc[available, "Value"].isna().any():
        raise ValueError("Available one-off evidence must include a value")
    if not evidence.loc[available, "Manual Classification"].isin(
        {"Recurring", "Non-recurring", "Uncertain"}
    ).all():
        raise ValueError("Available one-off evidence requires a valid classification")
    if not evidence.loc[available, "Manual Review Status"].eq("Reviewed").all():
        raise ValueError("Available one-off evidence must be manually reviewed")
    return evidence


def _bind_one_off_modules(
    bound_frame: pd.DataFrame,
    one_off_evidence: Optional[pd.DataFrame],
    to_canonical: dict[int, int],
) -> bool:
    """Bind either explicit evidence or an unavailable production placeholder."""

    if one_off_evidence is None:
        raw = _unavailable_one_offs(bound_frame)
        classified = raw.copy(deep=True)
        classified["Manual Classification"] = "Not Applicable"
        classified["Manual Review Status"] = "Not Applicable"
        evidence_available = False
    else:
        actual_years = set(to_canonical)
        classified = one_off_evidence.loc[
            one_off_evidence["Fiscal Year"].isin(actual_years)
        ].copy(deep=True)
        classified["Fiscal Year"] = classified["Fiscal Year"].replace(to_canonical)
        raw = classified.loc[:, list(_ONE_OFF_REQUIRED_FIELDS)].copy(deep=True)
        evidence_available = classified["Availability"].eq("Available").any()

    source = types.ModuleType("Data.one_off_items")
    source.required_fields = list(_ONE_OFF_REQUIRED_FIELDS)
    source.required_years = list(_CANONICAL_YEARS)
    source.required_categories = list(_ONE_OFF_CATEGORIES)
    source.one_off_items_df = raw
    sys.modules[source.__name__] = source

    classified_module = types.ModuleType("Analysis.manual_one_off_classification")
    classified_module.manual_one_off_classification_df = classified
    sys.modules[classified_module.__name__] = classified_module
    return evidence_available


def _unavailable_buybacks() -> types.ModuleType:
    module = types.ModuleType("Analysis.buyback_adjustment")
    module.buyback_adjustment_df = pd.DataFrame({
        "Fiscal Year": _CANONICAL_YEARS,
        "Shares Repurchased": [float("nan")] * 4,
        "Shares Issued Net": [float("nan")] * 4,
        "Net Share Effect": [float("nan")] * 4,
        "Net Share Effect Direction": ["N/A"] * 4,
        "Buyback Offset Ratio": [float("nan")] * 4,
        "Buyback Offset Ratio Display": ["N/A"] * 4,
        "Buyback Offset Classification": ["N/A"] * 4,
        "Cash Spent on Buybacks": [float("nan")] * 4,
        "Cash Spent Display": ["N/A"] * 4,
        "Shares Outstanding Growth": [float("nan")] * 4,
        "Shares Outstanding Growth Percentage": ["N/A"] * 4,
    })
    sys.modules[module.__name__] = module
    return module


def _unavailable_normalization_modules(company_frame: pd.DataFrame) -> None:
    reported_income = company_frame.loc[
        company_frame["Metric"].eq("Net Income"),
        ["Fiscal Year", "Value"],
    ].set_index("Fiscal Year")["Value"]
    normalized = types.ModuleType("Calculations.normalized_net_income")
    normalized.normalized_net_income_df = pd.DataFrame(columns=[
        "Fiscal Year", "Reported Net Income", "Non-recurring Gains Removed",
        "Non-recurring Charges Added Back", "Net Normalization Adjustment",
        "Normalized Net Income", "Normalized NI Difference",
        "Normalized NI Difference Percentage",
    ])
    sys.modules[normalized.__name__] = normalized

    comparison = types.ModuleType("Analysis.reported_vs_normalized_earnings")
    comparison.reported_vs_normalized_earnings_df = pd.DataFrame(columns=[
        "Fiscal Year", "Reported Net Income", "Normalized Net Income",
        "Difference", "Percentage Difference", "Percentage Difference Display",
        "Earnings Adjustment Direction",
    ])
    sys.modules[comparison.__name__] = comparison

    flags = types.ModuleType("Analysis.normalization_red_flags")
    flags.LARGE_DIFFERENCE_RULE = "abs(Percentage Difference) >= 10%"
    flags.LARGE_DIFFERENCE_THRESHOLD = 0.10
    flags.REPEATED_ONE_OFF_RULE = "Years Appearing >= 2"
    normalization_columns = [
        "Fiscal Year", "Reported Net Income", "Normalized Net Income",
        "Difference", "Percentage Difference", "Percentage Difference Display",
        "Earnings Adjustment Direction", "Large Difference Rule",
        "Large Normalization Difference Flag",
        "Large Normalization Difference Result",
        "Large Normalization Difference Severity",
        "One-Off Categories Identified", "Repeated Categories",
        "Repeated One-Off Rule", "Repeated One-Off Flag",
        "Repeated One-Off Result", "Repeated One-Off Severity",
        "Normalization Signal", "Overall Severity", "Explanation",
    ]
    flags.normalization_red_flags_df = pd.DataFrame(
        [
            {
                "Fiscal Year": year,
                "Reported Net Income": reported_income.get(year),
                "Normalized Net Income": None,
                "Difference": None, "Percentage Difference": None,
                "Percentage Difference Display": "N/A",
                "Earnings Adjustment Direction": "Unavailable",
                "Large Difference Rule": flags.LARGE_DIFFERENCE_RULE,
                "Large Normalization Difference Flag": None,
                "Large Normalization Difference Result": "Unavailable",
                "Large Normalization Difference Severity": None,
                "One-Off Categories Identified": "Unavailable",
                "Repeated Categories": "Unavailable",
                "Repeated One-Off Rule": flags.REPEATED_ONE_OFF_RULE,
                "Repeated One-Off Flag": None,
                "Repeated One-Off Result": "Unavailable",
                "Repeated One-Off Severity": None,
                "Normalization Signal": "Unavailable",
                "Overall Severity": None,
                "Explanation": (
                    "Normalized-earnings evidence was not independently "
                    "available for this company run."
                ),
            }
            for year in _CANONICAL_YEARS
        ],
        columns=normalization_columns,
    )
    sys.modules[flags.__name__] = flags


def _restore_fiscal_years(value: Any, year_map: dict[int, int]) -> Any:
    if isinstance(value, pd.DataFrame):
        result = value.copy(deep=True)
        if "Fiscal Year" in result.columns:
            result["Fiscal Year"] = result["Fiscal Year"].replace(year_map)
        return result
    return value


_NORMALIZATION_YEAR_TEXT_MARKERS = (
    "normaliz", "one-off", "one off", "raw data", "calculation",
    "explanation", "description", "category", "evidence", "narrative",
    "fiscal year", "classification", "review", "status", "result",
    "signal", "direction", "accounting effect",
)
_NORMALIZATION_PROVENANCE_COLUMNS = {
    "Company", "Ticker", "Source", "Source Date", "Source Detail", "Units",
}


def _restore_normalization_fiscal_years(
    value: Any, year_map: dict[int, int]
) -> Any:
    """Restore row years and canonical-year references in normalization text."""

    result = _restore_fiscal_years(value, year_map)
    if not isinstance(result, pd.DataFrame):
        return result
    replacements = {
        int(canonical): int(actual)
        for canonical, actual in year_map.items()
        if int(canonical) != int(actual)
    }
    if not replacements:
        return result
    year_pattern = re.compile(
        r"(?<!\d)(" + "|".join(map(str, sorted(replacements))) + r")(?!\d)"
    )

    def restore_text_years(item: Any) -> Any:
        if not isinstance(item, str):
            return item
        return year_pattern.sub(
            lambda match: str(replacements[int(match.group(1))]), item
        )

    for column in result.columns:
        normalized_name = str(column).strip().casefold()
        if column in _NORMALIZATION_PROVENANCE_COLUMNS:
            continue
        if any(marker in normalized_name for marker in _NORMALIZATION_YEAR_TEXT_MARKERS):
            result[column] = result[column].map(restore_text_years)
    return result


def _production_four_year_outputs(
    corrected_data: pd.DataFrame,
    *,
    one_off_evidence: Optional[pd.DataFrame] = None,
) -> dict[str, Any]:
    """Run one legacy four-period window against supplied company data."""

    if not isinstance(corrected_data, pd.DataFrame):
        raise TypeError("Production calculations require the corrected DataFrame")
    actual_years = tuple(sorted(int(year) for year in corrected_data["Fiscal Year"].unique()))
    if len(actual_years) < 4:
        raise ValueError("Existing analysis modules require four annual periods")
    analysis_years = actual_years[-4:]
    to_canonical = dict(zip(analysis_years, _CANONICAL_YEARS))
    from_canonical = {canonical: actual for actual, canonical in to_canonical.items()}
    bound_frame = corrected_data.loc[
        corrected_data["Fiscal Year"].isin(analysis_years)
    ].copy(deep=True)
    bound_frame["Fiscal Year"] = bound_frame["Fiscal Year"].replace(to_canonical)
    bound_frame["Metric"] = bound_frame["Metric"].replace(
        {"Income Tax Expense": "Tax Expense"}
    )
    for module_name in _DYNAMIC_ANALYSIS_MODULES:
        sys.modules.pop(module_name, None)
    sys.modules.pop("Data.one_off_items", None)
    with contextlib.redirect_stdout(io.StringIO()):
        source_module = importlib.import_module("Data.apple_test_dataset")
        source_module.apple_financial_data_df = bound_frame
        source_module.verified_values = {
            int(year): group.set_index("Metric")["Value"].to_dict()
            for year, group in bound_frame.groupby("Fiscal Year")
        }

        deferred_module = importlib.import_module("Data.deferred_tax_data")
        deferred_rows = bound_frame.loc[
            bound_frame["Metric"].isin(
                ["Deferred Tax Assets", "Deferred Tax Liabilities"]
            )
        ].copy()
        deferred_rows["Financial Statement"] = "Income Tax Note"
        deferred_rows["Availability"] = "Available"
        unavailable_tax_rows = []
        for year in _CANONICAL_YEARS:
            for metric in (
                "Current Tax Expense", "Deferred Tax Expense",
                "Tax-Loss Carryforwards",
            ):
                unavailable_tax_rows.append({
                    "Company": bound_frame.iloc[0]["Company"],
                    "Ticker": bound_frame.iloc[0]["Ticker"],
                    "Fiscal Year": year, "Metric": metric, "Value": None,
                    "Units": "Not Available",
                    "Financial Statement": "Income Tax Note",
                    "Source": "Not Available", "Source Date": "Not Available",
                    "Availability": "Not Available",
                })
        deferred_module.deferred_tax_data_df = pd.DataFrame(
            deferred_rows.reindex(
                columns=deferred_module.required_fields
            ).to_dict("records") + unavailable_tax_rows,
            columns=deferred_module.required_fields,
        )

        has_one_off_evidence = _bind_one_off_modules(
            bound_frame, one_off_evidence, to_canonical
        )

        calculation_modules = {
            name: importlib.import_module(name)
            for name in _DYNAMIC_ANALYSIS_MODULES
            if name.startswith("Calculations.")
            and name != "Calculations.normalized_net_income"
        }
        importlib.import_module("Analysis.repeated_one_off_detection")
        if has_one_off_evidence:
            importlib.import_module("Calculations.normalized_net_income")
            importlib.import_module("Analysis.reported_vs_normalized_earnings")
            importlib.import_module("Analysis.normalization_red_flags")
        else:
            _unavailable_normalization_modules(bound_frame)
        importlib.import_module("Analysis.inventory_warning")
        importlib.import_module("Analysis.ap_warning")
        importlib.import_module("Analysis.accrual_red_flags")
        importlib.import_module("Analysis.capex_rule")
        importlib.import_module("Analysis.dta_analysis")
        importlib.import_module("Analysis.dtl_analysis")
        importlib.import_module("Analysis.tax_red_flags")
        importlib.import_module("Analysis.sbc_vs_dilution")
        _unavailable_buybacks()
        importlib.import_module("Analysis.sbc_red_flags")
        importlib.import_module("Analysis.working_capital_red_flags")
        importlib.import_module("Analysis.red_flag_table")
        importlib.import_module("Analysis.severity_system")
        master_module = _module_prefix(
            "Analysis.master_analysis_table", "validation_errors"
        )

    return {
        "corrected_financial_data": corrected_data.copy(deep=True),
        "financial_summary": _restore_normalization_fiscal_years(
            master_module.master_analysis_df, from_canonical
        ),
        "cash_conversion": _restore_fiscal_years(
            sys.modules["Analysis.accrual_red_flags"].accrual_red_flags_df,
            from_canonical,
        ),
        "normalized_earnings": _restore_normalization_fiscal_years(
            sys.modules["Analysis.normalization_red_flags"].normalization_red_flags_df,
            from_canonical,
        ),
        "fiscal_year_map": from_canonical,
        "calculation_tables": {
            name: _restore_fiscal_years(
                next(
                    value for key, value in vars(module).items()
                    if key.endswith("_df") and isinstance(value, pd.DataFrame)
                ),
                from_canonical,
            )
            for name, module in calculation_modules.items()
        },
        "analysis_tables": {
            "working_capital": _restore_fiscal_years(
                sys.modules["Analysis.working_capital_red_flags"].working_capital_red_flags_df,
                from_canonical,
            ),
            "taxes": _restore_fiscal_years(
                sys.modules["Analysis.tax_red_flags"].tax_red_flags_df,
                from_canonical,
            ),
            "sbc": _restore_fiscal_years(
                sys.modules["Analysis.sbc_red_flags"].sbc_red_flags_df,
                from_canonical,
            ),
            "red_flags": _restore_normalization_fiscal_years(
                sys.modules["Analysis.red_flag_table"].red_flag_table_df,
                from_canonical,
            ),
        },
        "excel_support_tables": {
            "accrual": _restore_fiscal_years(
                sys.modules["Analysis.accrual_red_flags"].accrual_red_flags_df,
                from_canonical,
            ),
            "capex": _restore_fiscal_years(
                sys.modules["Analysis.capex_rule"].capex_rule_df,
                from_canonical,
            ),
            "dta": _restore_fiscal_years(
                sys.modules["Analysis.dta_analysis"].dta_analysis_df,
                from_canonical,
            ),
            "dtl": _restore_fiscal_years(
                sys.modules["Analysis.dtl_analysis"].dtl_analysis_df,
                from_canonical,
            ),
            "manual_one_offs": _restore_normalization_fiscal_years(
                sys.modules["Analysis.manual_one_off_classification"].manual_one_off_classification_df,
                from_canonical,
            ),
            "normalized_net_income": _restore_normalization_fiscal_years(
                sys.modules["Calculations.normalized_net_income"].normalized_net_income_df,
                from_canonical,
            ),
            "deferred_tax_data": _restore_fiscal_years(
                sys.modules["Data.deferred_tax_data"].deferred_tax_data_df,
                from_canonical,
            ),
        },
    }


def _combined_year_table(
    frames: Iterable[pd.DataFrame], *, identity: Tuple[str, ...]
) -> pd.DataFrame:
    """Combine overlapping module outputs without changing their values."""

    available = [frame for frame in frames if isinstance(frame, pd.DataFrame)]
    if not available:
        return pd.DataFrame()
    combined = pd.concat(available, ignore_index=True)
    keys = [column for column in identity if column in combined.columns]
    if keys:
        non_key_columns = [
            column for column in combined.columns if column not in keys
        ]
        combined["_Available Field Count"] = combined[
            non_key_columns
        ].notna().sum(axis=1)
        combined = combined.sort_values(
            [*keys, "_Available Field Count"],
            ascending=[True] * len(keys) + [False],
            kind="stable",
        )
        combined = combined.drop_duplicates(subset=keys, keep="first").drop(
            columns="_Available Field Count"
        )
        combined = combined.sort_values(keys, kind="stable")
    return combined.reset_index(drop=True)


_PARTIAL_CORE_METRICS = (
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
    "Deferred Tax Assets",
    "Deferred Tax Liabilities",
    "Tax Expense",
)


def _apply_partial_availability(
    outputs: dict[str, Any], corrected_data: pd.DataFrame
) -> dict[str, Any]:
    """Neutralize only outputs whose required evidence is missing."""

    years = tuple(sorted(int(year) for year in corrected_data["Fiscal Year"].unique()))
    normalized_metric = corrected_data["Metric"].replace(
        {"Income Tax Expense": "Tax Expense"}
    )
    present = {
        (str(metric), int(year)): value
        for metric, year, value in zip(
            normalized_metric,
            corrected_data["Fiscal Year"],
            corrected_data["Value"],
        )
    }
    missing_facts = {
        (metric, year)
        for year in years
        for metric in _PARTIAL_CORE_METRICS
        if (metric, year) not in present or pd.isna(present[(metric, year)])
    }
    if not missing_facts:
        outputs["unavailable_outputs"] = pd.DataFrame(
            columns=[
                "Analysis",
                "Fiscal Year",
                "Output",
                "Status",
                "Missing Metric",
                "Missing Fiscal Year",
                "Explanation",
            ]
        )
        return outputs

    unavailable_rows: list[dict[str, Any]] = []

    def required(
        fiscal_year: int,
        metrics: Iterable[str],
        *,
        include_prior: bool = False,
    ) -> tuple[tuple[str, int], ...]:
        required_years = (fiscal_year - 1, fiscal_year) if include_prior else (fiscal_year,)
        return tuple(
            sorted(
                fact
                for fact in missing_facts
                if fact[0] in set(metrics) and fact[1] in required_years
            )
        )

    def message(facts: tuple[tuple[str, int], ...]) -> str:
        evidence = ", ".join(f"{metric} (FY {year})" for metric, year in facts)
        return f"Unavailable because validated evidence is missing: {evidence}."

    def record(
        analysis_name: str,
        fiscal_year: int,
        output_name: str,
        facts: tuple[tuple[str, int], ...],
    ) -> None:
        for metric, missing_year in facts:
            unavailable_rows.append(
                {
                    "Analysis": analysis_name,
                    "Fiscal Year": fiscal_year,
                    "Output": output_name,
                    "Status": "Unavailable",
                    "Missing Metric": metric,
                    "Missing Fiscal Year": missing_year,
                    "Explanation": message(facts),
                }
            )

    def unavailable_fields(
        frame: pd.DataFrame,
        fiscal_year: int,
        fields: Iterable[str],
        facts: tuple[tuple[str, int], ...],
        *,
        text_fields: Iterable[str] = (),
    ) -> None:
        if not facts or "Fiscal Year" not in frame.columns:
            return
        mask = frame["Fiscal Year"].eq(fiscal_year)
        text = set(text_fields)
        for field in fields:
            if field in frame.columns:
                if field not in text and pd.api.types.is_bool_dtype(frame[field]):
                    frame[field] = frame[field].astype(object)
                frame.loc[mask, field] = "Unavailable" if field in text else None
        if "Missing Evidence" not in frame.columns:
            frame["Missing Evidence"] = None
        frame.loc[mask, "Missing Evidence"] = message(facts)

    summary = outputs.get("financial_summary")
    if isinstance(summary, pd.DataFrame):
        raw_columns = {metric: metric for metric in _PARTIAL_CORE_METRICS}
        growth_dependencies = {
            "Revenue Growth": ("Revenue",),
            "Net Income Growth": ("Net Income",),
            "OCF Growth": ("Operating Cash Flow",),
            "D&A Growth": ("Depreciation & Amortization",),
            "CapEx Growth": ("Capital Expenditures",),
            "SBC Growth": ("Stock-Based Compensation",),
            "Shares Outstanding Growth": ("Shares Outstanding",),
            "AR Growth": ("Accounts Receivable",),
            "Inventory Growth": ("Inventory",),
            "AP Growth": ("Accounts Payable",),
            "DTA Growth": ("Deferred Tax Assets",),
            "DTL Growth": ("Deferred Tax Liabilities",),
        }
        same_year_dependencies = {
            "Free Cash Flow": ("Operating Cash Flow", "Capital Expenditures"),
            "D&A / Revenue": ("Depreciation & Amortization", "Revenue"),
            "CapEx / Revenue": ("Capital Expenditures", "Revenue"),
            "CapEx / D&A": ("Capital Expenditures", "Depreciation & Amortization"),
            "SBC / Revenue": ("Stock-Based Compensation", "Revenue"),
            "SBC / OCF": ("Stock-Based Compensation", "Operating Cash Flow"),
            "SBC / Net Income": ("Stock-Based Compensation", "Net Income"),
            "DTA / Net Income": ("Deferred Tax Assets", "Net Income"),
        }
        for fiscal_year in years:
            for column, metric in raw_columns.items():
                facts = required(fiscal_year, (metric,))
                unavailable_fields(summary, fiscal_year, (column,), facts)
                if facts:
                    record("Financial Summary", fiscal_year, column, facts)
            for column, metrics in growth_dependencies.items():
                facts = required(fiscal_year, metrics, include_prior=True)
                unavailable_fields(summary, fiscal_year, (column,), facts)
                if facts:
                    record("Financial Summary", fiscal_year, column, facts)
            for column, metrics in same_year_dependencies.items():
                facts = required(fiscal_year, metrics)
                unavailable_fields(summary, fiscal_year, (column,), facts)
                if facts:
                    record("Financial Summary", fiscal_year, column, facts)
            ar_facts = required(
                fiscal_year, ("Accounts Receivable", "Revenue"), include_prior=True
            )
            ni_ocf_facts = required(
                fiscal_year, ("Net Income", "Operating Cash Flow"), include_prior=True
            )
            inventory_facts = required(
                fiscal_year, ("Inventory", "Revenue"), include_prior=True
            )
            ap_facts = required(
                fiscal_year,
                ("Accounts Payable", "Revenue", "Operating Cash Flow"),
                include_prior=True,
            )
            wc_facts = required(
                fiscal_year,
                ("Accounts Receivable", "Inventory", "Accounts Payable"),
                include_prior=True,
            )
            capex_facts = required(
                fiscal_year, ("Capital Expenditures", "Depreciation & Amortization")
            )
            compensation_facts = required(
                fiscal_year, ("Stock-Based Compensation", "Net Income")
            )
            dilution_facts = required(
                fiscal_year, ("Shares Outstanding",), include_prior=True
            )
            dta_risk_facts = tuple(sorted(set(
                required(fiscal_year, ("Deferred Tax Assets",))
                + required(fiscal_year, ("Net Income",), include_prior=True)
            )))
            tax_movement_facts = required(
                fiscal_year,
                ("Deferred Tax Assets", "Deferred Tax Liabilities"),
                include_prior=True,
            )
            component_groups = (
                (
                    ("AR Revenue Gap", "AR Flag"), ar_facts, ()
                ),
                (("NI OCF Flag",), ni_ocf_facts, ()),
                (
                    ("Combined Accrual Flag", "Accrual Signal", "Accrual Severity"),
                    tuple(sorted(set(ar_facts + ni_ocf_facts))),
                    ("Accrual Signal", "Accrual Severity"),
                ),
                (
                    ("Inventory Flag", "Inventory Severity"),
                    inventory_facts,
                    ("Inventory Severity",),
                ),
                (
                    ("AP Classification", "AP Result", "AP Severity"),
                    ap_facts,
                    ("AP Classification", "AP Result", "AP Severity"),
                ),
                (
                    (
                        "AR Change", "Inventory Change", "AP Change",
                        "Net Working Capital Cash Effect", "Working Capital Cash Use",
                        "Working Capital Signal", "Working Capital Severity",
                    ),
                    wc_facts,
                    ("Working Capital Signal", "Working Capital Severity"),
                ),
                (
                    ("CapEx Investigation Result",),
                    capex_facts,
                    ("CapEx Investigation Result",),
                ),
                (("Large SBC Flag",), compensation_facts, ()),
                (("Dilution Flag",), dilution_facts, ()),
                (
                    ("SBC Signal", "SBC Severity"),
                    tuple(sorted(set(compensation_facts + dilution_facts))),
                    ("SBC Signal", "SBC Severity"),
                ),
                (
                    ("DTA Risk Result", "DTA Risk Flag"),
                    dta_risk_facts,
                    ("DTA Risk Result",),
                ),
                (
                    ("Deferred Tax Movement Flag",),
                    tax_movement_facts,
                    (),
                ),
                (
                    ("Tax Signal", "Tax Severity"),
                    tuple(sorted(set(dta_risk_facts + tax_movement_facts))),
                    ("Tax Signal", "Tax Severity"),
                ),
            )
            affected_summary_facts: tuple[tuple[str, int], ...] = ()
            for fields, facts, text_fields in component_groups:
                unavailable_fields(
                    summary,
                    fiscal_year,
                    fields,
                    facts,
                    text_fields=text_fields,
                )
                affected_summary_facts = tuple(
                    sorted(set(affected_summary_facts + facts))
                )
            if affected_summary_facts:
                unavailable_fields(
                    summary,
                    fiscal_year,
                    (
                        "High-Level Severity", "Material Concern Count",
                        "Needs Investigation Count", "Low Risk Count",
                    ),
                    affected_summary_facts,
                    text_fields=("High-Level Severity",),
                )

    cash = outputs.get("cash_conversion")
    if isinstance(cash, pd.DataFrame):
        for fiscal_year in cash["Fiscal Year"].astype(int):
            ar_facts = required(
                fiscal_year, ("Accounts Receivable", "Revenue"), include_prior=True
            )
            ni_facts = required(
                fiscal_year,
                ("Net Income", "Operating Cash Flow"),
                include_prior=True,
            )
            unavailable_fields(
                cash,
                fiscal_year,
                ("AR Growth", "Revenue Growth", "AR Revenue Gap", "AR Flag"),
                ar_facts,
            )
            unavailable_fields(
                cash,
                fiscal_year,
                ("Net Income Growth", "OCF Growth", "NI OCF Flag"),
                ni_facts,
            )
            combined = tuple(sorted(set(ar_facts + ni_facts)))
            unavailable_fields(
                cash,
                fiscal_year,
                ("Combined Accrual Flag", "Accrual Signal", "Severity", "Explanation"),
                combined,
                text_fields=("Accrual Signal", "Severity", "Explanation"),
            )
            if combined:
                cash.loc[cash["Fiscal Year"].eq(fiscal_year), "Explanation"] = message(combined)
                record("Cash Conversion", fiscal_year, "Accrual assessment", combined)

    analysis_tables = outputs.get("analysis_tables", {})
    working = analysis_tables.get("working_capital")
    if isinstance(working, pd.DataFrame):
        for fiscal_year in working["Fiscal Year"].astype(int):
            inventory_facts = required(
                fiscal_year, ("Inventory", "Revenue"), include_prior=True
            )
            ap_facts = required(
                fiscal_year,
                ("Accounts Payable", "Revenue", "Operating Cash Flow"),
                include_prior=True,
            )
            wc_facts = required(
                fiscal_year,
                ("Accounts Receivable", "Inventory", "Accounts Payable"),
                include_prior=True,
            )
            unavailable_fields(
                working,
                fiscal_year,
                (
                    "Inventory Growth", "Inventory Revenue Gap", "Inventory Flag",
                    "Inventory Result", "Inventory Severity",
                ),
                inventory_facts,
                text_fields=("Inventory Result", "Inventory Severity"),
            )
            unavailable_fields(
                working,
                fiscal_year,
                ("AP Growth", "OCF Growth", "AP Revenue Gap", "AP Classification", "AP Result", "AP Severity"),
                ap_facts,
                text_fields=("AP Classification", "AP Result", "AP Severity"),
            )
            unavailable_fields(
                working,
                fiscal_year,
                (
                    "AR Change", "Inventory Change", "AP Change",
                    "Net Working Capital Cash Effect", "WC Calculation",
                    "Working Capital Cash Use", "WC Classification", "WC Result",
                    "WC Severity",
                ),
                wc_facts,
                text_fields=("WC Calculation", "WC Classification", "WC Result", "WC Severity"),
            )
            overall = tuple(sorted(set(inventory_facts + ap_facts + wc_facts)))
            unavailable_fields(
                working,
                fiscal_year,
                ("Working Capital Signal", "Overall Severity", "Explanation"),
                overall,
                text_fields=("Working Capital Signal", "Overall Severity", "Explanation"),
            )
            if overall:
                working.loc[working["Fiscal Year"].eq(fiscal_year), "Explanation"] = message(overall)
                record("Working Capital", fiscal_year, "Overall assessment", overall)

    taxes = analysis_tables.get("taxes")
    if isinstance(taxes, pd.DataFrame):
        for fiscal_year in taxes["Fiscal Year"].astype(int):
            dta_facts = tuple(sorted(set(
                required(fiscal_year, ("Deferred Tax Assets",))
                + required(fiscal_year, ("Net Income",), include_prior=True)
            )))
            dta_growth_facts = required(
                fiscal_year, ("Deferred Tax Assets",), include_prior=True
            )
            dtl_growth_facts = required(
                fiscal_year, ("Deferred Tax Liabilities",), include_prior=True
            )
            movement_facts = tuple(sorted(set(dta_growth_facts + dtl_growth_facts)))
            unavailable_fields(
                taxes,
                fiscal_year,
                ("DTA / Net Income", "DTA Risk Flag", "DTA Result", "DTA Severity"),
                dta_facts,
                text_fields=("DTA Result", "DTA Severity"),
            )
            unavailable_fields(
                taxes,
                fiscal_year,
                ("DTA Growth", "DTA Movement Trigger"),
                dta_growth_facts,
            )
            unavailable_fields(
                taxes,
                fiscal_year,
                ("DTL Growth", "DTL Movement Trigger"),
                dtl_growth_facts,
            )
            unavailable_fields(
                taxes,
                fiscal_year,
                (
                    "Deferred Tax Movement Flag",
                    "Deferred Tax Movement Classification",
                    "Deferred Tax Movement Result", "Deferred Tax Movement Severity",
                ),
                movement_facts,
                text_fields=(
                    "Deferred Tax Movement Classification",
                    "Deferred Tax Movement Result",
                    "Deferred Tax Movement Severity",
                ),
            )
            overall = tuple(sorted(set(dta_facts + movement_facts)))
            unavailable_fields(
                taxes,
                fiscal_year,
                ("Tax Signal", "Overall Tax Severity", "Explanation"),
                overall,
                text_fields=("Tax Signal", "Overall Tax Severity", "Explanation"),
            )
            if overall:
                taxes.loc[taxes["Fiscal Year"].eq(fiscal_year), "Explanation"] = message(overall)
                record("Deferred Taxes", fiscal_year, "Overall assessment", overall)

    sbc = analysis_tables.get("sbc")
    if isinstance(sbc, pd.DataFrame):
        for fiscal_year in sbc["Fiscal Year"].astype(int):
            compensation_facts = required(
                fiscal_year, ("Stock-Based Compensation", "Net Income")
            )
            dilution_facts = required(
                fiscal_year, ("Shares Outstanding",), include_prior=True
            )
            unavailable_fields(
                sbc,
                fiscal_year,
                ("SBC", "Net Income", "SBC / Net Income", "Large SBC Flag", "Large SBC Result", "Large SBC Severity"),
                compensation_facts,
                text_fields=("Large SBC Result", "Large SBC Severity"),
            )
            unavailable_fields(
                sbc,
                fiscal_year,
                ("Shares Outstanding", "Shares Outstanding Growth", "Dilution Flag", "Dilution Result", "Dilution Severity"),
                dilution_facts,
                text_fields=("Dilution Result", "Dilution Severity"),
            )
            overall = tuple(sorted(set(compensation_facts + dilution_facts)))
            unavailable_fields(
                sbc,
                fiscal_year,
                ("SBC Signal", "Overall SBC Severity", "Explanation"),
                overall,
                text_fields=("SBC Signal", "Overall SBC Severity", "Explanation"),
            )
            if overall:
                sbc.loc[sbc["Fiscal Year"].eq(fiscal_year), "Explanation"] = message(overall)
                record("Stock-Based Compensation", fiscal_year, "Overall assessment", overall)

    normalized = outputs.get("normalized_earnings")
    if isinstance(normalized, pd.DataFrame):
        for fiscal_year in normalized["Fiscal Year"].astype(int):
            facts = required(fiscal_year, ("Net Income",))
            unavailable_fields(
                normalized,
                fiscal_year,
                (
                    "Reported Net Income", "Normalized Net Income", "Difference",
                    "Percentage Difference", "Large Normalization Difference Flag",
                    "Large Normalization Difference Result",
                    "Large Normalization Difference Severity", "Normalization Signal",
                    "Overall Severity", "Explanation",
                ),
                facts,
                text_fields=(
                    "Large Normalization Difference Result",
                    "Large Normalization Difference Severity", "Normalization Signal",
                    "Overall Severity", "Explanation",
                ),
            )
            if facts:
                normalized.loc[normalized["Fiscal Year"].eq(fiscal_year), "Explanation"] = message(facts)
                record("Normalized Earnings", fiscal_year, "Reported earnings evidence", facts)

    red_flags = analysis_tables.get("red_flags")
    red_flag_dependencies = {
        "AR growth vs Revenue growth": (("Accounts Receivable", "Revenue"), True),
        "Net Income growth vs OCF growth": (("Net Income", "Operating Cash Flow"), True),
        "Inventory growth vs Revenue growth": (("Inventory", "Revenue"), True),
        "Accounts Payable pattern": (("Accounts Payable", "Revenue", "Operating Cash Flow"), True),
        "Selected-account working-capital proxy": (
            ("Accounts Receivable", "Inventory", "Accounts Payable"),
            True,
        ),
        "CapEx vs D&A": (("Capital Expenditures", "Depreciation & Amortization"), False),
        "Deferred Tax Asset risk": ((), False),
        "Deferred tax movement": (("Deferred Tax Assets", "Deferred Tax Liabilities"), True),
        "Large SBC": (("Stock-Based Compensation", "Net Income"), False),
        "SBC dilution": (("Shares Outstanding",), True),
        "Buyback offset": ((), False),
        "Large normalization difference": (("Net Income",), False),
        "Repeated one-off items": ((), False),
    }
    if isinstance(red_flags, pd.DataFrame):
        if "Missing Evidence" not in red_flags.columns:
            red_flags["Missing Evidence"] = None
        for index, row in red_flags.iterrows():
            dependency = red_flag_dependencies.get(str(row.get("Metric")))
            if dependency is None:
                continue
            metrics, include_prior = dependency
            fiscal_year = int(row["Fiscal Year"])
            facts = required(fiscal_year, metrics, include_prior=include_prior)
            if str(row.get("Metric")) == "Deferred Tax Asset risk":
                facts = tuple(sorted(set(
                    required(fiscal_year, ("Deferred Tax Assets",))
                    + required(fiscal_year, ("Net Income",), include_prior=True)
                )))
            if not facts:
                continue
            unavailable_columns = [
                column
                for column in (
                    "Raw Data",
                    "Calculation",
                    "Result",
                    "Severity",
                    "Internal Severity",
                    "Final Severity",
                )
                if column in red_flags.columns
            ]
            red_flags.loc[index, unavailable_columns] = "Unavailable"
            red_flags.loc[index, "Explanation"] = message(facts)
            red_flags.loc[index, "Missing Evidence"] = message(facts)
            record("Red Flags", fiscal_year, str(row["Metric"]), facts)

    outputs["unavailable_outputs"] = (
        pd.DataFrame(unavailable_rows)
        .drop_duplicates()
        .sort_values(["Fiscal Year", "Analysis", "Output", "Missing Metric"])
        .reset_index(drop=True)
    )
    return outputs


def _production_calculation_outputs(
    corrected_data: pd.DataFrame,
    *,
    one_off_evidence: Optional[pd.DataFrame] = None,
) -> dict[str, Any]:
    """Run the existing four-period modules across up to five annual periods."""

    if not isinstance(corrected_data, pd.DataFrame):
        raise TypeError("Production calculations require the corrected DataFrame")
    validated_one_off_evidence = _validated_one_off_evidence(
        corrected_data, one_off_evidence
    )
    fiscal_years = tuple(
        sorted(int(year) for year in corrected_data["Fiscal Year"].unique())
    )
    if len(fiscal_years) < 4:
        raise ValueError("Existing analysis modules require four annual periods")
    if len(fiscal_years) > 10:
        fiscal_years = fiscal_years[-10:]

    windows = tuple(
        fiscal_years[position : position + 4]
        for position in range(len(fiscal_years) - 3)
    )
    window_outputs = []
    for window in windows:
        window_frame = corrected_data.loc[
            corrected_data["Fiscal Year"].isin(window)
        ].copy(deep=True)
        window_outputs.append(_production_four_year_outputs(
            window_frame,
            one_off_evidence=validated_one_off_evidence,
        ))

    calculation_names = set().union(
        *(output["calculation_tables"].keys() for output in window_outputs)
    )
    combined_calculations = {
        name: _combined_year_table(
            [
                output["calculation_tables"][name]
                for output in window_outputs
                if name in output["calculation_tables"]
            ],
            identity=("Fiscal Year",),
        )
        for name in calculation_names
    }
    combined_analysis = {
        "working_capital": _combined_year_table(
            [output["analysis_tables"]["working_capital"] for output in window_outputs],
            identity=("Fiscal Year",),
        ),
        "taxes": _combined_year_table(
            [output["analysis_tables"]["taxes"] for output in window_outputs],
            identity=("Fiscal Year",),
        ),
        "sbc": _combined_year_table(
            [output["analysis_tables"]["sbc"] for output in window_outputs],
            identity=("Fiscal Year",),
        ),
        "red_flags": _combined_year_table(
            [output["analysis_tables"]["red_flags"] for output in window_outputs],
            identity=("Fiscal Year", "Metric"),
        ),
    }
    combined_excel_support = {
        name: _combined_year_table(
            [output["excel_support_tables"][name] for output in window_outputs],
            identity=(
                ("Fiscal Year", "Category")
                if name == "manual_one_offs"
                else ("Fiscal Year", "Metric")
                if name == "deferred_tax_data"
                else ("Fiscal Year",)
            ),
        )
        for name in window_outputs[0]["excel_support_tables"]
    }
    outputs = {
        "corrected_financial_data": corrected_data.loc[
            corrected_data["Fiscal Year"].isin(fiscal_years)
        ].copy(deep=True),
        "financial_summary": _combined_year_table(
            [output["financial_summary"] for output in window_outputs],
            identity=("Fiscal Year",),
        ),
        "cash_conversion": _combined_year_table(
            [output["cash_conversion"] for output in window_outputs],
            identity=("Fiscal Year",),
        ),
        "normalized_earnings": _combined_year_table(
            [output["normalized_earnings"] for output in window_outputs],
            identity=("Fiscal Year",),
        ),
        "calculation_tables": combined_calculations,
        "analysis_tables": combined_analysis,
        "excel_support_tables": combined_excel_support,
    }
    return _apply_partial_availability(outputs, corrected_data)


def _production_red_flag_outputs(calculations: dict[str, Any]) -> dict[str, Any]:
    """Return existing flag and severity tables without reclassifying results."""

    if "financial_summary" not in calculations:
        raise ValueError("Existing calculation outputs are required")
    combined = calculations["analysis_tables"]
    red_flags_module = types.ModuleType("Analysis.red_flag_table")
    red_flags_module.red_flag_table_df = combined["red_flags"].copy(deep=True)
    sys.modules[red_flags_module.__name__] = red_flags_module
    sys.modules.pop("Analysis.severity_system", None)
    partial = red_flags_module.red_flag_table_df["Result"].eq("Unavailable").any()
    if partial:
        red_flags = red_flags_module.red_flag_table_df
        severity_mapping = {
            "None": "Low Risk",
            "Low": "Needs Investigation",
            "Medium": "Needs Investigation",
            "High": "Material Concern",
            "Unavailable": "Unavailable",
        }
        if {"Internal Severity", "Final Severity"}.issubset(red_flags.columns):
            detailed_severity = red_flags[
                [
                    "Fiscal Year",
                    "Metric",
                    "Result",
                    "Internal Severity",
                    "Final Severity",
                    "Explanation",
                ]
            ].copy(deep=True)
        else:
            detailed_severity = red_flags[
                ["Fiscal Year", "Metric", "Result", "Severity", "Explanation"]
            ].rename(columns={"Severity": "Internal Severity"})
            detailed_severity["Final Severity"] = detailed_severity[
                "Internal Severity"
            ].map(severity_mapping).fillna("Unavailable")
        detailed_severity = detailed_severity[
            [
                "Fiscal Year", "Metric", "Result", "Internal Severity",
                "Final Severity", "Explanation",
            ]
        ]
        priority = {"Low Risk": 0, "Needs Investigation": 1, "Material Concern": 2}
        fiscal_rows = []
        for fiscal_year, rows in detailed_severity.groupby("Fiscal Year", sort=True):
            available_severities = [
                value for value in rows["Final Severity"] if value in priority
            ]
            strongest = (
                max(available_severities, key=priority.get)
                if available_severities
                else "Unavailable"
            )
            has_unavailable = rows["Final Severity"].eq("Unavailable").any()
            high_level = (
                "Unavailable"
                if has_unavailable and strongest == "Low Risk"
                else strongest
            )
            triggered = rows.loc[
                rows["Result"].isin(("Flag", "Review")), "Metric"
            ].drop_duplicates().tolist()
            missing_metrics = rows.loc[
                rows["Result"].eq("Unavailable"), "Metric"
            ].tolist()
            explanation = (
                "Some rule results are unavailable because validated evidence is missing. "
                "Available triggered results retain their existing severity; missing "
                "evidence is not treated as a clean result."
                if has_unavailable
                else "Available rule results retain the existing severity mapping."
            )
            fiscal_rows.append(
                {
                    "Fiscal Year": int(fiscal_year),
                    "High-Level Severity": high_level,
                    "Material Concern Count": int(rows["Final Severity"].eq("Material Concern").sum()),
                    "Needs Investigation Count": int(rows["Final Severity"].eq("Needs Investigation").sum()),
                    "Low Risk Count": int(rows["Final Severity"].eq("Low Risk").sum()),
                    "Unavailable Count": int(rows["Final Severity"].eq("Unavailable").sum()),
                    "Triggered Metrics": "; ".join(triggered) if triggered else "None",
                    "Unavailable Metrics": "; ".join(missing_metrics) if missing_metrics else "None",
                    "Explanation": explanation,
                }
            )
        fiscal_severity = pd.DataFrame(fiscal_rows)
        available_overall = [
            value for value in fiscal_severity["High-Level Severity"] if value in priority
        ]
        strongest_overall = (
            max(available_overall, key=priority.get)
            if available_overall
            else "Unavailable"
        )
        any_unavailable = fiscal_severity["Unavailable Count"].gt(0).any()
        benchmark = (
            "Unavailable"
            if any_unavailable and strongest_overall == "Low Risk"
            else strongest_overall
        )
        overall_severity = pd.DataFrame(
            [
                {
                    "Benchmark Severity": benchmark,
                    "Availability": "Partial" if any_unavailable else "Complete",
                    "Explanation": (
                        "Some evidence is unavailable. Available concerns retain their "
                        "existing severity, but missing evidence is not classified as "
                        "No Flag or Low Risk."
                        if any_unavailable
                        else "All severity evidence is available."
                    ),
                }
            ]
        )
        severity_module = types.ModuleType("Analysis.severity_system")
        severity_module.SEVERITY_MAPPING = severity_mapping
        severity_module.benchmark_severity = benchmark
        severity_module.detailed_severity_table_df = detailed_severity
        severity_module.fiscal_year_severity_summary_df = fiscal_severity
        severity_module.benchmark_severity_df = overall_severity
        sys.modules[severity_module.__name__] = severity_module
    else:
        with contextlib.redirect_stdout(io.StringIO()):
            severity_module = importlib.import_module("Analysis.severity_system")
        detailed_severity = severity_module.detailed_severity_table_df.copy(deep=True)
        fiscal_severity = severity_module.fiscal_year_severity_summary_df.copy(deep=True)
        overall_severity = severity_module.benchmark_severity_df.copy(deep=True)
    outputs = {
        "working_capital": combined["working_capital"].copy(deep=True),
        "taxes": combined["taxes"].copy(deep=True),
        "sbc": combined["sbc"].copy(deep=True),
        "red_flags": combined["red_flags"].copy(deep=True),
        "detailed_severity": detailed_severity,
        "fiscal_year_severity": fiscal_severity,
        "overall_severity": overall_severity,
        "unavailable_outputs": calculations.get("unavailable_outputs", pd.DataFrame()).copy(deep=True),
    }
    for module_name, attribute, frame in (
        ("Analysis.accrual_red_flags", "accrual_red_flags_df", calculations["excel_support_tables"]["accrual"]),
        ("Analysis.capex_rule", "capex_rule_df", calculations["excel_support_tables"]["capex"]),
        ("Analysis.dta_analysis", "dta_analysis_df", calculations["excel_support_tables"]["dta"]),
        ("Analysis.dtl_analysis", "dtl_analysis_df", calculations["excel_support_tables"]["dtl"]),
        ("Analysis.working_capital_red_flags", "working_capital_red_flags_df", outputs["working_capital"]),
        ("Analysis.tax_red_flags", "tax_red_flags_df", outputs["taxes"]),
        ("Analysis.sbc_red_flags", "sbc_red_flags_df", outputs["sbc"]),
        ("Analysis.normalization_red_flags", "normalization_red_flags_df", calculations["normalized_earnings"]),
        ("Analysis.manual_one_off_classification", "manual_one_off_classification_df", calculations["excel_support_tables"]["manual_one_offs"]),
        ("Calculations.normalized_net_income", "normalized_net_income_df", calculations["excel_support_tables"]["normalized_net_income"]),
        ("Data.deferred_tax_data", "deferred_tax_data_df", calculations["excel_support_tables"]["deferred_tax_data"]),
    ):
        module = sys.modules.get(module_name) or types.ModuleType(module_name)
        setattr(module, attribute, frame.copy(deep=True))
        sys.modules[module_name] = module
    master_module = sys.modules.get("Analysis.master_analysis_table") or types.ModuleType(
        "Analysis.master_analysis_table"
    )
    master_module.master_analysis_df = calculations["financial_summary"].copy(deep=True)
    master_module.analyst_summary_df = calculations["financial_summary"].copy(deep=True)
    sys.modules[master_module.__name__] = master_module
    source_module = sys.modules.get("Data.apple_test_dataset")
    if source_module is not None:
        source_module.apple_financial_data_df = calculations[
            "corrected_financial_data"
        ].copy(deep=True)
    return outputs


def _production_structured_input(
    company: Any,
    validation: AnalysisValidationGateResult,
    corrected_data: pd.DataFrame,
    calculations: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    """Call the Task 90 packager with the existing analysis tables."""

    from Analysis.ai_input_preparation import build_ai_analysis_input

    requested_years = set(validation.requested_fiscal_years)

    def requested(frame: pd.DataFrame) -> pd.DataFrame:
        if "Fiscal Year" not in frame.columns:
            return frame.copy(deep=True)
        return frame.loc[frame["Fiscal Year"].isin(requested_years)].copy()

    packaging_validation = validation
    if validation.decision is AnalysisDecision.STOP or not validation.can_analyze:
        packaging_validation = replace(
            validation,
            decision=AnalysisDecision.CONTINUE,
            can_analyze=True,
        )
    structured = build_ai_analysis_input(
        company_name=company.company_name,
        ticker=company.ticker,
        validation_gate=packaging_validation,
        financial_summary_df=requested(calculations["financial_summary"]),
        cash_conversion_df=requested(calculations["cash_conversion"]),
        working_capital_df=requested(analysis["working_capital"]),
        taxes_df=requested(analysis["taxes"]),
        sbc_df=requested(analysis["sbc"]),
        normalized_earnings_df=requested(calculations["normalized_earnings"]),
        red_flags_df=requested(analysis["red_flags"]),
        detailed_severity_df=requested(analysis["detailed_severity"]),
        fiscal_year_severity_df=requested(analysis["fiscal_year_severity"]),
        overall_severity_df=analysis["overall_severity"],
    )
    unavailable = analysis.get("unavailable_outputs", pd.DataFrame())
    if isinstance(unavailable, pd.DataFrame) and not unavailable.empty:
        structured["partial_analysis"] = {
            "status": "Partial",
            "unavailable_outputs": unavailable.to_dict("records"),
            "notice": (
                "Some outputs are Unavailable because validated metric-year "
                "evidence is missing or invalid. No values were estimated, "
                "inferred, substituted, or invented."
            ),
        }
    return structured


def _production_interpretations(structured_input: dict[str, Any]) -> dict[str, Any]:
    """Run Tasks 91-97 using only the Task 90 structured input."""

    from Analysis.accrual_interpretation import interpret_accrual_quality
    from Analysis.capex_interpretation import interpret_capex
    from Analysis.deferred_tax_interpretation import interpret_deferred_taxes
    from Analysis.final_earnings_quality_conclusion import (
        build_final_earnings_quality_conclusion,
    )
    from Analysis.normalized_earnings_interpretation import (
        interpret_normalized_earnings,
    )
    from Analysis.sbc_interpretation import interpret_sbc
    from Analysis.working_capital_interpretation import interpret_working_capital

    outputs = {
        "accrual": interpret_accrual_quality(structured_input),
        "working_capital": interpret_working_capital(structured_input),
        "capex": interpret_capex(structured_input),
        "deferred_taxes": interpret_deferred_taxes(structured_input),
        "sbc": interpret_sbc(structured_input),
        "normalized_earnings": interpret_normalized_earnings(structured_input),
    }
    outputs["final_conclusion"] = build_final_earnings_quality_conclusion(
        **outputs,
        existing_overall_severity=structured_input["overall_assessment"][
            "overall_severity"
        ],
    )
    partial = structured_input.get("partial_analysis")
    if partial:
        unavailable = partial.get("unavailable_outputs", [])
        evidence = "; ".join(dict.fromkeys(
            f"{item['Missing Metric']} (FY {item['Missing Fiscal Year']})"
            for item in unavailable
        ))
        available_explanation = outputs["final_conclusion"].get(
            "explanation", "Available validated results were summarized."
        )
        outputs["final_conclusion"] = {
            **outputs["final_conclusion"],
            "analysis_status": "Partial Analysis",
            "explanation": (
                "Partial Analysis: this conclusion uses only available validated "
                f"analysis results. {available_explanation} Important missing "
                f"metric-year evidence: {evidence}. Analyses that depend on this "
                "evidence remain Unavailable and were not treated as No Flag, Low "
                "Risk, zero, or another clean result. This conclusion may change "
                "if verified missing values are added through the correction panel "
                "and the analysis is rerun."
            ),
        }
    return outputs


def _production_excel_output(
    company: Any,
    _corrected_data: Any,
    _calculations: Any,
    _analysis: Any,
    _structured_input: Any,
    interpretations: Any,
    validation: Any,
) -> Any:
    """Present the finalized same-run pipeline outputs in one workbook."""

    from Analysis.excel_export import (
        PRODUCTION_SHEET_ORDER,
        export_pipeline_result,
    )

    required_columns = {"Company", "Ticker", "Fiscal Year", "Metric", "Value"}
    if (
        not isinstance(_corrected_data, pd.DataFrame)
        or _corrected_data.empty
        or not required_columns.issubset(_corrected_data.columns)
    ):
        raise ValueError("Corrected financial data is unavailable for Excel generation")
    workbook_years = _selected_fiscal_years(_corrected_data["Fiscal Year"])
    workbook_companies = {
        str(value).casefold() for value in _corrected_data["Company"].dropna().unique()
    }
    workbook_tickers = {
        str(value).casefold() for value in _corrected_data["Ticker"].dropna().unique()
    }
    if workbook_companies != {str(company.company_name).casefold()}:
        raise ValueError("Corrected financial data does not match the selected company")
    if workbook_tickers != {str(company.ticker).casefold()}:
        raise ValueError("Corrected financial data does not match the selected ticker")
    if validation is None:
        raise TypeError("validation is required for production Excel generation")
    if not isinstance(_structured_input, Mapping):
        raise TypeError(
            "structured_ai_input must be a finalized mapping for production Excel generation"
        )

    conclusion = interpretations.get("final_conclusion", {})
    if _structured_input.get("partial_analysis"):
        valid_partial_conclusions = {
            "Strong", "Generally Healthy", "Needs Investigation", "Weak"
        }
        if conclusion.get("earnings_quality_conclusion") not in valid_partial_conclusions:
            raise ValueError(
                "Partial-analysis conclusion must preserve a supported category"
            )
        if conclusion.get("analysis_status") != "Partial Analysis":
            raise ValueError("Partial-analysis status is missing from the conclusion")

    output_path = export_pipeline_result(
        output_path=_final_workbook_path(company, workbook_years),
        company=company,
        company_name=str(company.company_name),
        ticker=str(company.ticker),
        fiscal_years=workbook_years,
        corrected_data=_corrected_data,
        calculations=_calculations,
        analysis=_analysis,
        validation=validation,
        structured_ai_input=_structured_input,
        interpretations=interpretations,
    )
    if (
        output_path.suffix.casefold() != ".xlsx"
        or not output_path.is_file()
        or output_path.stat().st_size == 0
    ):
        raise ValueError("The final Excel workbook was not created")
    workbook = load_workbook(output_path, read_only=True, data_only=False)
    try:
        if tuple(workbook.sheetnames) != PRODUCTION_SHEET_ORDER:
            raise ValueError("The final Excel workbook has unexpected worksheets")
        expected_identity = f"{company.company_name} ({company.ticker})"
        expected_years = ", ".join(str(year) for year in workbook_years)
        if workbook["Dashboard"]["A2"].value != expected_identity:
            raise ValueError("The final Excel workbook company does not match")
        if workbook["Dashboard"]["A8"].value != expected_years:
            raise ValueError("The final Excel workbook fiscal years do not match")
        if workbook["Analyst Conclusion"]["A2"].value != expected_identity:
            raise ValueError("The final Excel conclusion company does not match")
        if workbook["Dashboard"]["A4"].value != "Overall Severity":
            raise ValueError("The overall severity label is missing")
        if workbook["Dashboard"]["A10"].value != (
            "Final Earnings-Quality Conclusion"
        ):
            raise ValueError("The final conclusion label is missing")
        if _structured_input.get("partial_analysis"):
            conclusion_sheet = workbook["Analyst Conclusion"]
            if conclusion_sheet["A8"].value != conclusion.get(
                "earnings_quality_conclusion"
            ):
                raise ValueError(
                    "The partial Excel conclusion category was not preserved"
                )
            if "partial analysis" not in str(
                conclusion_sheet["A14"].value
            ).casefold():
                raise ValueError("The partial Excel conclusion disclosure is missing")
    finally:
        workbook.close()
    return output_path


def create_production_pipeline_modules(
    *,
    user_agent: Optional[str] = None,
    one_off_evidence: Optional[pd.DataFrame] = None,
) -> PipelineModules:
    """Bind the controller to the project's existing production modules."""

    configured_user_agent = user_agent or os.environ.get("SEC_USER_AGENT")
    production_fetcher: Optional[SECFinancialStatementFetcher] = None

    def client() -> SECFinancialStatementFetcher:
        nonlocal production_fetcher
        if production_fetcher is None:
            production_fetcher = _sec_fetcher(configured_user_agent)
        return production_fetcher

    def production_identify(query: str) -> Any:
        return identify_official_company(query, fetcher=client())

    def production_extract(company: Any, years: int) -> Any:
        if not configured_user_agent:
            raise ValueError(
                "SEC_USER_AGENT is required for official SEC extraction"
            )
        fetcher = client()
        available = fetcher.fetch(company)
        context_year_count = max(years, 4)
        selected_years = tuple(
            sorted({value.fiscal_year for value in available.values})[
                -context_year_count:
            ]
        )
        return fetcher.fetch(company, fiscal_years=selected_years)

    def production_validate(
        statements: Any, _years: int, corrections: Tuple[Any, ...]
    ) -> AnalysisValidationGateResult:
        frame = _financial_statements_frame(statements)
        usable_years = tuple(sorted(int(year) for year in frame["Fiscal Year"].unique()))
        if len(usable_years) < 4:
            issue = BlockingIssue(
                metric="Annual filing history",
                fiscal_year=usable_years[-1] if usable_years else 0,
                validation_source="Task 109 fiscal-year availability",
                blocking_status="INSUFFICIENT_ANNUAL_HISTORY",
                explanation=(
                    "At least four usable SEC annual fiscal years are required; "
                    f"only {len(usable_years)} were available."
                ),
                manual_correction_used=False,
            )
            return AnalysisValidationGateResult(
                decision=AnalysisDecision.STOP,
                can_analyze=False,
                requested_fiscal_years=usable_years,
                blocking_issues=(issue,),
                metric_year_results=(),
                blocking_issue_count=1,
            )
        requested_years = tuple(
            sorted(frame["Fiscal Year"].unique())[-_years:]
        )
        year_ends = {}
        for year in requested_years:
            period_ends = frame.loc[
                frame["Fiscal Year"].eq(year), "Period End"
            ].dropna()
            if not period_ends.empty:
                year_ends[int(year)] = max(str(value) for value in period_ends)
        return evaluate_integrated_annual_dataset(
            frame,
            requested_fiscal_years=requested_years,
            fiscal_year_end_dates=year_ends,
            corrections=corrections,
        )

    def production_apply_corrections(
        statements: Any, corrections: Tuple[Any, ...]
    ) -> pd.DataFrame:
        frame = _financial_statements_frame(statements)
        return _apply_correction_overlay(frame, corrections)
        
    def production_calculations(corrected_data: pd.DataFrame) -> dict[str, Any]:
        return _production_calculation_outputs(
            corrected_data,
            one_off_evidence=one_off_evidence,
        )

    return PipelineModules(
        identify_company=production_identify,
        extract_data=production_extract,
        validate_data=production_validate,
        apply_manual_corrections=production_apply_corrections,
        run_calculations=production_calculations,
        run_red_flags_and_severity=_production_red_flag_outputs,
        build_structured_ai_input=_production_structured_input,
        run_interpretations=_production_interpretations,
        generate_excel=_production_excel_output,
    )


def run_pipeline(
    company_or_ticker: str,
    number_of_fiscal_years: int,
    *,
    modules: Optional[PipelineModules] = None,
    manual_corrections: Iterable[Any] = (),
    user_agent: Optional[str] = None,
    one_off_evidence: Optional[pd.DataFrame] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> PipelineResult:
    """Run the production pipeline unless explicit test modules are supplied."""

    configured_modules = modules or create_production_pipeline_modules(
        user_agent=user_agent,
        one_off_evidence=one_off_evidence,
    )
    return EarningsQualityController(configured_modules).run(
        company_or_ticker,
        number_of_fiscal_years,
        manual_corrections=manual_corrections,
        progress_callback=progress_callback,
    )


__all__ = [
    "EarningsQualityController",
    "PIPELINE_STAGES",
    "PipelineModules",
    "PipelineResult",
    "PipelineStageError",
    "ProgressCallback",
    "SUPPORTED_COMPANIES",
    "SupportedCompany",
    "available_fiscal_years",
    "create_production_pipeline_modules",
    "downloadable_workbook_path",
    "identify_official_company",
    "pipeline_result_matches_selection",
    "run_pipeline",
    "search_supported_company_options",
    "sec_company_options",
]
