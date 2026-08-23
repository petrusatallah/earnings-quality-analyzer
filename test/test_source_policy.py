"""Tests for Task 70 source classification policy."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.source_policy import SourceClassification, classify_source


def test_task_70_source_policy() -> None:
    assert classify_source("https://sec.gov") == SourceClassification.PRIMARY
    assert (
        classify_source("https://finance.yahoo.com")
        == SourceClassification.SECONDARY
    )
    assert (
        classify_source("https://annualreports.com")
        == SourceClassification.SECONDARY
    )
    assert (
        classify_source("https://random-finance-blog.com")
        == SourceClassification.UNAPPROVED
    )
    assert (
        classify_source(
            "https://investor.apple.com",
            official_company_source=True,
        )
        == SourceClassification.PRIMARY
    )
    assert (
        classify_source(
            "https://example-company.com/filings/company.xbrl",
            company_filed_xbrl=True,
        )
        == SourceClassification.PRIMARY
    )
    assert (
        classify_source("https://unknown-investor-website.example")
        == SourceClassification.UNAPPROVED
    )

    print("Task 70 source policy tests passed")


if __name__ == "__main__":
    test_task_70_source_policy()
