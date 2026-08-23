"""Conservative potential one-off candidate extraction for Task 81."""

from dataclasses import dataclass, replace
from enum import Enum
import html
import re
from typing import Any, Iterable, Mapping, Optional, Tuple, Union

from Data.company_identifier import CompanyIdentity, normalize_ticker_input
from Data.financial_statement_fetcher import (
    ANNUAL_FORMS,
    AnnualFinancialStatements,
    SECFinancialStatementFetcher,
)
from Data.provenance import ProvenanceMixin


class OneOffStatus(str, Enum):
    CANDIDATE_FOUND = "CANDIDATE FOUND"
    NEEDS_VALIDATION = "NEEDS VALIDATION"
    NONE_FOUND = "NONE FOUND"


@dataclass(frozen=True)
class OfficialFilingDocument:
    company_name: str
    ticker: str
    cik: str
    fiscal_year: int
    filing_form: str
    filing_date: str
    accession_number: str
    source_url: str
    content: str


@dataclass(frozen=True)
class OneOffCandidate(ProvenanceMixin):
    fiscal_year: int
    candidate_name: str
    category: Optional[str]
    raw_amount: Any
    raw_unit: Optional[str]
    normalized_usd_millions: Optional[float]
    impact_direction: Optional[str]
    xbrl_concept: Optional[str]
    filing_form: Optional[str]
    filing_date: Optional[str]
    accession_number: Optional[str]
    filing_section_or_note: Optional[str]
    source_url: Optional[str]
    source_evidence: Optional[str]
    status: OneOffStatus
    validation_reason: Optional[str] = None


_CATEGORY_PATTERNS = (
    ("Restructuring", re.compile(r"\brestructur(?:ing|ed|e)\b.{0,80}\b(?:charge|cost|expense|recorded|incurred|payment)s?\b|\b(?:charge|cost|expense|recorded|incurred|payment)s?\b.{0,80}\brestructur(?:ing|ed|e)\b", re.I)),
    ("Impairment or Write-Down", re.compile(r"\b(?:impairment charge|impairment loss|recorded an? impairment|one-time write[- ]?down|major write[- ]?down|material write[- ]?down|significant write[- ]?down)\b", re.I)),
    ("Litigation or Settlement", re.compile(r"\b(?:litigation|lawsuit|legal settlement|settlement of (?:a |the )?(?:lawsuit|claim|case|dispute))\b.{0,120}\b(?:charge|expense|gain|loss|recorded|incurred|paid|payment|award)s?\b|\b(?:charge|expense|gain|loss|recorded|incurred|paid|payment|award)s?\b.{0,120}\b(?:litigation|lawsuit|legal settlement|settlement of (?:a |the )?(?:lawsuit|claim|case|dispute))\b", re.I)),
    ("Regulatory Fine or Decision", re.compile(r"\bstate aid decision\b.{0,100}\b(?:charge|expense|payable|payment)s?\b|\b(?:charge|expense|payable|payment)s?\b.{0,100}\bstate aid decision\b|\b(?:regulatory|commission|authority)\b.{0,100}\b(?:fine|charge|penalty|payment)s?\b|\b(?:fine|penalty)\b.{0,100}\b(?:imposed|paid|recorded|incurred)\b", re.I)),
    ("Acquisition-Related", re.compile(r"\bacquisition[- ]related\b", re.I)),
    ("Asset-Sale Gain or Loss", re.compile(r"\b(?:gain|loss) on (?:the )?sale\b", re.I)),
    ("Discontinued Operations", re.compile(r"\bdiscontinued operation", re.I)),
    ("Unusual Tax Charge or Benefit", re.compile(r"\b(?:one-time|unusual).{0,40}\b(?:tax charge|tax benefit)\b|\b(?:tax charge|tax benefit).{0,40}\b(?:one-time|unusual)\b", re.I)),
    ("Other Unusual Item", re.compile(r"\bone-time\b|\b(?:nonrecurring|non-recurring|unusual)\b.{0,40}\b(?:charge|gain|loss|expense|item|benefit)\b", re.I)),
)

_ORDINARY_PATTERNS = re.compile(
    r"\bordinary course\b|\brecurring payroll\b|\bregular payroll\b|"
    r"\bcost of revenue\b|\bnormal operating expense\b",
    re.I,
)
_HYPOTHETICAL_PATTERNS = re.compile(
    r"^\s*if\b|\bmore likely than not\b|"
    r"\bmay be subject to\b|\bcould (?:result|lead|require|adversely)\b|"
    r"\bmight (?:result|lead|require)\b|\bpotential(?:ly)?\b|"
    r"\bmay differ from\b|\bonce .{0,80}\b(?:determined|identified)\b|"
    r"\bif .{0,120}\b(?:would|could|may|recognize|record)\b",
    re.I,
)
_ACCOUNTING_POLICY_PATTERNS = re.compile(
    r"\bwhen\b.{0,240}\b(?:is|are) (?:recorded|recognized|measured)\b|"
    r"\b(?:is|are) (?:recorded|recognized|measured)\b.{0,160}\bwhen\b|"
    r"\baccounting policy\b|\bwe test .{0,120}\bfor impairment\b",
    re.I,
)
_ACTUAL_EVENT_PATTERNS = re.compile(
    r"\b(?:recorded|recognized|incurred|charged|realized|paid|settled|imposes|imposed|"
    r"entered into|agreed to|resulted in|includes? charges?)\b|"
    r"\b(?:one-time|nonrecurring|non-recurring|unusual)\s+"
    r"(?:(?:income\s+)?tax\s+)?(?:charge|expense|gain|loss|benefit)\b|"
    r"\b(?:charge|expense|gain|loss|fine|penalty|benefit)\s+of\b",
    re.I,
)
_AMOUNT_PATTERN = re.compile(
    r"(?P<currency>\$|USD|€|EUR|£|GBP)\s*"
    r"(?P<number>\(?-?\d[\d,]*(?:\.\d+)?\)?)\s*"
    r"(?P<scale>billion|million|thousand)?",
    re.I,
)
_IX_FACT_PATTERN = re.compile(
    r"<ix:nonfraction\b(?P<attrs>[^>]*)>(?P<value>.*?)</ix:nonfraction>",
    re.I | re.S,
)
_NAME_ATTR_PATTERN = re.compile(r"\bname=[\"']([^\"']+)[\"']", re.I)
_BLOCK_SPLIT_PATTERN = re.compile(r"</(?:div|p|tr|li|h[1-6])\s*>", re.I)


def retrieve_official_annual_filing_document(
    fetcher: SECFinancialStatementFetcher,
    annual_statements: AnnualFinancialStatements,
    fiscal_year: int,
) -> OfficialFilingDocument:
    """Retrieve a filing document through the existing SEC client and cache."""

    annual_values = tuple(
        value
        for value in annual_statements.for_fiscal_year(fiscal_year)
        if value.accession_number and value.filing_form in ANNUAL_FORMS
    )
    if not annual_values:
        raise ValueError(f"No annual filing metadata exists for fiscal year {fiscal_year}.")
    metadata = max(annual_values, key=lambda value: value.filing_date or "")
    accession = metadata.accession_number
    submissions_url = (
        f"https://data.sec.gov/submissions/CIK{annual_statements.cik}.json"
    )
    submissions = fetcher.get_official_json(submissions_url)
    primary_document = _find_primary_document(submissions, accession)

    if primary_document is None:
        filings = submissions.get("filings", {})
        older_files = filings.get("files", ()) if isinstance(filings, Mapping) else ()
        for item in older_files if isinstance(older_files, Iterable) else ():
            if not isinstance(item, Mapping) or not item.get("name"):
                continue
            older = fetcher.get_official_json(
                f"https://data.sec.gov/submissions/{item['name']}"
            )
            primary_document = _find_primary_document(older, accession)
            if primary_document:
                break
    if primary_document is None:
        raise ValueError(f"SEC submission metadata lacks a primary document for {accession}.")

    source_url = f"{metadata.source_url}{primary_document}"
    return OfficialFilingDocument(
        company_name=annual_statements.company_name,
        ticker=annual_statements.ticker,
        cik=annual_statements.cik,
        fiscal_year=fiscal_year,
        filing_form=metadata.filing_form,
        filing_date=metadata.filing_date,
        accession_number=accession,
        source_url=source_url,
        content=fetcher.get_official_filing_text(source_url),
    )


def _find_primary_document(
    submissions: Mapping[str, Any], accession: str
) -> Optional[str]:
    recent = submissions.get("filings", {}).get("recent", submissions)
    if not isinstance(recent, Mapping):
        return None
    accessions = recent.get("accessionNumber", ())
    documents = recent.get("primaryDocument", ())
    if not isinstance(accessions, list) or not isinstance(documents, list):
        return None
    for item_accession, document in zip(accessions, documents):
        if item_accession == accession and isinstance(document, str) and document:
            return document
    return None


def extract_potential_one_offs(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
    filing_document: OfficialFilingDocument,
) -> Tuple[OneOffCandidate, ...]:
    """Find review candidates without concluding they are non-recurring."""

    ticker = company.ticker if isinstance(company, CompanyIdentity) else company
    normalized_ticker = normalize_ticker_input(ticker)
    if normalized_ticker != normalize_ticker_input(annual_statements.ticker):
        raise ValueError("Company input does not match the Task 72 annual statements.")
    if normalized_ticker != normalize_ticker_input(filing_document.ticker):
        raise ValueError("Filing document does not match the requested company.")
    if fiscal_year != filing_document.fiscal_year:
        raise ValueError("Filing document does not match the requested fiscal year.")

    found = []
    for raw_block in _BLOCK_SPLIT_PATTERN.split(filing_document.content):
        plain = _plain_text(raw_block)
        for sentence in _sentences(plain):
            if not sentence or _ORDINARY_PATTERNS.search(sentence):
                continue
            category = _category(sentence)
            if category is None:
                continue
            if not _is_actual_event(sentence):
                continue
            found.append(
                _candidate_from_block(
                    raw_block, sentence, category, filing_document
                )
            )

    deduplicated = _deduplicate_candidates(found)
    if deduplicated:
        return deduplicated
    return (
        OneOffCandidate(
            fiscal_year=fiscal_year,
            candidate_name="No potential one-off candidates identified",
            category=None,
            raw_amount=None,
            raw_unit=None,
            normalized_usd_millions=None,
            impact_direction=None,
            xbrl_concept=None,
            filing_form=filing_document.filing_form,
            filing_date=filing_document.filing_date,
            accession_number=filing_document.accession_number,
            filing_section_or_note=None,
            source_url=filing_document.source_url,
            source_evidence=None,
            status=OneOffStatus.NONE_FOUND,
        ),
    )


def _plain_text(raw_html: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", raw_html)
    return " ".join(html.unescape(without_tags).replace("\xa0", " ").split())


def _sentences(text: str) -> Tuple[str, ...]:
    return tuple(
        item.strip()
        for item in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
        if item.strip()
    )


def _category(text: str) -> Optional[str]:
    matches = [name for name, pattern in _CATEGORY_PATTERNS if pattern.search(text)]
    if "Unusual Tax Charge or Benefit" in matches:
        return "Unusual Tax Charge or Benefit"
    if "Regulatory Fine or Decision" in matches and "tax" in text.lower():
        return "Unusual Tax Charge or Benefit"
    return matches[0] if matches else None


def _is_actual_event(text: str) -> bool:
    if _HYPOTHETICAL_PATTERNS.search(text) or _ACCOUNTING_POLICY_PATTERNS.search(text):
        return False
    return bool(_ACTUAL_EVENT_PATTERNS.search(text))


def _has_fiscal_year_earnings_impact(text: str) -> bool:
    """Require evidence that the disclosed event affected the selected year's results."""

    lowered = text.lower()
    actual_recognition = bool(
        re.search(r"\b(?:recorded|recognized|incurred|charged|realized)\b", lowered)
        or re.search(r"\bone-time\b.{0,50}\b(?:charge|expense|gain|loss|benefit)\b", lowered)
    )
    earnings_term = bool(
        re.search(
            r"\b(?:income|expense|tax|earnings|results? of operations|charge|gain|loss|benefit)\b",
            lowered,
        )
    )
    return actual_recognition and earnings_term


def _candidate_from_block(
    raw_block: str,
    text: str,
    category: str,
    document: OfficialFilingDocument,
) -> OneOffCandidate:
    bundled = _is_bundled_disclosure(text)
    if bundled:
        category = "Bundled Unusual Items"
    amount_match = _AMOUNT_PATTERN.search(text)
    raw_amount = raw_unit = normalized = disclosed_number = None
    if amount_match:
        disclosed_number = amount_match.group("number")
        negative = disclosed_number.startswith("(") and disclosed_number.endswith(")")
        number = float(disclosed_number.strip("()").replace(",", ""))
        if negative:
            number = -number
        scale = (amount_match.group("scale") or "").lower()
        multiplier = {"billion": 1_000_000_000, "million": 1_000_000, "thousand": 1_000}.get(scale, 1)
        raw_amount = number * multiplier
        currency = amount_match.group("currency").upper()
        raw_unit = {"$": "USD", "USD": "USD", "€": "EUR", "EUR": "EUR", "£": "GBP", "GBP": "GBP"}[currency]
        normalized = raw_amount / 1_000_000 if raw_unit == "USD" else None

    concept = _xbrl_concept_for_amount(raw_block, disclosed_number)
    if concept is None:
        concept = _xbrl_concept_near_unusual_amount(
            document.content, disclosed_number, category
        )
    direction = _impact_direction(text)
    earnings_relevant = _has_fiscal_year_earnings_impact(text)
    name_match = re.search(r"related to (?:the )?([^,.;()]+)", text, re.I)
    if name_match:
        candidate_name = re.split(
            r"\s+\b(?:was|were|is|are|has|had)\b\s+",
            name_match.group(1).strip(),
            maxsplit=1,
            flags=re.I,
        )[0]
        candidate_name = re.split(
            r"\s+and\s+(?=[$€£\d])", candidate_name, maxsplit=1, flags=re.I
        )[0].strip()
    else:
        candidate_name = category
    note_match = re.search(r"\b(Note\s+\d+[^,.;)]*)", text, re.I)
    status = (
        OneOffStatus.CANDIDATE_FOUND
        if raw_amount is not None and direction is not None and not bundled and earnings_relevant
        else OneOffStatus.NEEDS_VALIDATION
    )
    return OneOffCandidate(
        fiscal_year=document.fiscal_year,
        candidate_name=candidate_name,
        category=category,
        raw_amount=raw_amount,
        raw_unit=raw_unit,
        normalized_usd_millions=normalized,
        impact_direction=direction,
        xbrl_concept=concept,
        filing_form=document.filing_form,
        filing_date=document.filing_date,
        accession_number=document.accession_number,
        filing_section_or_note=note_match.group(1) if note_match else None,
        source_url=document.source_url,
        source_evidence=_short_evidence(text),
        status=status,
        validation_reason=(
            None
            if status is OneOffStatus.CANDIDATE_FOUND
            else (
                "The disclosed amount covers multiple unusual components and "
                "was not assigned to any single category."
                if bundled
                else (
                    "The event occurred, but its effect on the selected fiscal year's earnings is unclear."
                    if not earnings_relevant
                    else "An actual unusual event was found, but amount or earnings direction requires validation."
                )
            )
        ),
    )


def _is_bundled_disclosure(text: str) -> bool:
    components = set()
    lowered = text.lower()
    if re.search(r"\blitigation\b|\blawsuit\b|\bsettlement\b", lowered):
        components.add("legal")
    if re.search(r"\btax dispute", lowered):
        components.add("tax dispute")
    if re.search(r"\brestructur|\bseverance", lowered):
        components.add("restructuring")
    if re.search(r"\bimpairment|\bwrite[- ]?down", lowered):
        components.add("impairment")
    if re.search(r"\bacquisition[- ]related", lowered):
        components.add("acquisition")
    disclosed_amounts = tuple(_AMOUNT_PATTERN.finditer(text))
    return len(components) > 1 and len(disclosed_amounts) == 1


def _xbrl_concept_for_amount(raw_block: str, disclosed_number: Optional[str]) -> Optional[str]:
    if disclosed_number is None:
        return None
    target = disclosed_number.strip("()").replace(",", "")
    for match in _IX_FACT_PATTERN.finditer(raw_block):
        value = _plain_text(match.group("value")).replace(",", "")
        if value != target:
            continue
        name_match = _NAME_ATTR_PATTERN.search(match.group("attrs"))
        if name_match:
            return name_match.group(1)
    return None


def _xbrl_concept_near_unusual_amount(
    document: str,
    disclosed_number: Optional[str],
    category: str,
) -> Optional[str]:
    if disclosed_number is None:
        return None
    target = disclosed_number.strip("()").replace(",", "")
    for match in _IX_FACT_PATTERN.finditer(document):
        value = _plain_text(match.group("value")).replace(",", "")
        if value != target:
            continue
        nearby = _plain_text(
            document[max(0, match.start() - 350) : match.end() + 350]
        )
        if _category(nearby) != category:
            continue
        name_match = _NAME_ATTR_PATTERN.search(match.group("attrs"))
        if name_match:
            return name_match.group(1)
    return None


def _impact_direction(text: str) -> Optional[str]:
    lowered = text.lower()
    if re.search(r"\bcharge\b|\bexpense\b|\bloss\b|\bfine\b|\bwrite[- ]?down\b", lowered):
        return "Decreases income / increases expense"
    if re.search(r"\bgain\b|\bbenefit\b", lowered):
        return "Increases income / decreases expense"
    return None


def _short_evidence(text: str) -> str:
    words = text.split()
    return " ".join(words[:40]) + ("…" if len(words) > 40 else "")


def _dedupe_key(candidate: OneOffCandidate) -> Tuple[str, str]:
    name = re.sub(r"[^a-z0-9]+", " ", candidate.candidate_name.casefold()).strip()
    return candidate.category or "", name


def _deduplicate_candidates(
    candidates: Iterable[OneOffCandidate],
) -> Tuple[OneOffCandidate, ...]:
    grouped: dict[Tuple[str, str], list[OneOffCandidate]] = {}
    for candidate in candidates:
        key = _dedupe_key(candidate)
        matching_key = next(
            (
                existing_key
                for existing_key, group in grouped.items()
                if _same_event(group[0], candidate)
            ),
            None,
        )
        grouped.setdefault(matching_key or key, []).append(candidate)

    results = []
    for group in grouped.values():
        amounts = {
            (item.raw_amount, item.raw_unit)
            for item in group
            if item.raw_amount is not None
        }
        if len(amounts) > 1:
            best = max(group, key=lambda item: (bool(item.xbrl_concept), len(item.source_evidence or "")))
            results.append(
                replace(
                    best,
                    raw_amount=None,
                    raw_unit=None,
                    normalized_usd_millions=None,
                    status=OneOffStatus.NEEDS_VALIDATION,
                    validation_reason="Conflicting disclosed amounts exist for the same event.",
                )
            )
            continue
        best = max(
            group,
            key=lambda item: (
                item.status is OneOffStatus.CANDIDATE_FOUND,
                bool(item.xbrl_concept),
                bool(item.impact_direction),
                bool(item.filing_section_or_note),
                -len(item.source_evidence or ""),
            ),
        )
        results.append(best)
    return tuple(results)


def _same_event(first: OneOffCandidate, second: OneOffCandidate) -> bool:
    if first.category != second.category:
        return False
    first_name = _dedupe_key(first)[1]
    second_name = _dedupe_key(second)[1]
    generic_name = _dedupe_key(first)[0].casefold()
    if (first.raw_amount is None) != (second.raw_amount is None):
        specific = second if first.raw_amount is None else first
        generic = first if first.raw_amount is None else second
        specific_tokens = set(_dedupe_key(specific)[1].split()) - {
            "the", "a", "an", "of", "with", "and", "related", "to"
        }
        evidence_tokens = set(
            re.sub(
                r"[^a-z0-9]+", " ", (generic.source_evidence or "").casefold()
            ).split()
        )
        if specific_tokens and len(specific_tokens & evidence_tokens) / len(specific_tokens) >= 0.7:
            return True
    names_match = (
        first_name == second_name
        or first_name in second_name
        or second_name in first_name
    )
    if names_match and first_name != generic_name:
        return True
    ignored = {"the", "a", "an", "of", "with", "and", "related", "to"}
    first_tokens = set(first_name.split()) - ignored
    second_tokens = set(second_name.split()) - ignored
    token_match = bool(first_tokens and second_tokens) and (
        len(first_tokens & second_tokens) / len(first_tokens | second_tokens) >= 0.6
    )
    if token_match and first_name != generic_name and second_name != generic_name:
        return True

    # Generic category names alone do not establish that two disclosures are
    # the same event. Require the same disclosed amount and similar evidence.
    if first.raw_unit != second.raw_unit or first.raw_amount != second.raw_amount:
        return False
    first_evidence = set(re.sub(r"[^a-z0-9]+", " ", (first.source_evidence or "").casefold()).split()) - ignored
    second_evidence = set(re.sub(r"[^a-z0-9]+", " ", (second.source_evidence or "").casefold()).split()) - ignored
    return bool(first_evidence and second_evidence) and (
        len(first_evidence & second_evidence) / len(first_evidence | second_evidence) >= 0.45
    )
