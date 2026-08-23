"""Source policy for validated financial statement data.

Core financial statement numbers must come from primary sources.  Secondary
sources may provide context or cross-checks, but must never replace a primary
source.  Unknown sources are unapproved by default.

This module only describes and classifies sources; it performs no web access.
"""

from enum import Enum
from urllib.parse import urlparse


class SourceClassification(str, Enum):
    """Permitted source classifications."""

    PRIMARY = "Primary"
    SECONDARY = "Secondary"
    UNAPPROVED = "Unapproved"


# Highest priority first. Company-filed XBRL is listed separately because it
# may be delivered through either an investor-relations site or a regulator.
CORE_FINANCIAL_SOURCE_PRIORITY = (
    "Official company Investor Relations pages and annual reports",
    "Official regulatory filings (SEC/EDGAR or an equivalent regulator)",
    "Company-filed XBRL data, when available",
)


_OFFICIAL_REGULATOR_DOMAINS = frozenset(
    {
        "sec.gov",             # United States (SEC/EDGAR)
        "sedarplus.ca",       # Canada
        "companieshouse.gov.uk",
        "fca.org.uk",         # United Kingdom
        "asx.com.au",         # Australia, official exchange filings
        "bundesanzeiger.de",  # Germany
        "cnmv.es",            # Spain
        "amf-france.org",     # France
        "fsa.go.jp",          # Japan (EDINET regulator)
        "hkexnews.hk",        # Hong Kong exchange filings
        "sgx.com",            # Singapore exchange filings
    }
)

_SECONDARY_FINANCE_DOMAINS = frozenset(
    {
        "annualreports.com",
        "bloomberg.com",
        "finance.yahoo.com",
        "google.com",
        "investing.com",
        "macrotrends.net",
        "marketwatch.com",
        "morningstar.com",
        "reuters.com",
        "stockanalysis.com",
    }
)


def _hostname(source: str) -> str:
    value = source.strip()
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").lower().rstrip(".")


def _matches_domain(hostname: str, domains: frozenset[str]) -> bool:
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in domains)


def classify_source(
    source: str,
    *,
    official_company_source: bool = False,
    company_filed_xbrl: bool = False,
    third_party_reference: bool = False,
) -> SourceClassification:
    """Classify a source without fetching it.

    ``official_company_source`` should be set only after confirming that the
    URL belongs to the company's own Investor Relations site or annual-report
    archive. ``company_filed_xbrl`` means the data was filed by the company,
    not transformed or republished by a third party. Third-party sites are
    secondary even if they reproduce an official filing.

    Anything that cannot be positively identified is unapproved. This
    fail-closed behavior prevents a plausible-looking URL from becoming a
    validated source merely because it contains words such as "investor".
    """

    if not isinstance(source, str) or not source.strip():
        return SourceClassification.UNAPPROVED

    hostname = _hostname(source)

    # Known third-party domains cannot be promoted by caller flags.
    if _matches_domain(hostname, _SECONDARY_FINANCE_DOMAINS):
        return SourceClassification.SECONDARY

    if third_party_reference:
        return SourceClassification.SECONDARY

    if _matches_domain(hostname, _OFFICIAL_REGULATOR_DOMAINS):
        return SourceClassification.PRIMARY

    if official_company_source or company_filed_xbrl:
        return SourceClassification.PRIMARY

    return SourceClassification.UNAPPROVED
