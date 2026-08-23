"""Fixed, independently reviewable Apple benchmark answers for Task 99.

This file intentionally contains literals only.  It must not import or call
production calculation, analysis, extraction, or validation modules.
"""


MANUAL_VERIFIED_ANSWER_SHEET = {
    "benchmark": {
        "company": "Apple Inc.",
        "ticker": "AAPL",
        "fiscal_years": [2022, 2023, 2024, 2025],
        "purpose": "Fixed manual verification benchmark; not a calculation engine.",
        "value_policy": (
            "Values, units, rules, statuses, flags, and severities are transcribed "
            "from the existing project benchmark and validated outputs."
        ),
    },
    "raw_financial_data": {
        2022: {
            "source": {
                "name": "Apple Form 10-K",
                "source_date": "2022-10-28",
                "provenance": "Existing Data/apple_test_dataset.py Apple benchmark",
            },
            "data": {
                "Revenue": {"value": 394328, "units": "USD millions", "financial_statement": "Income Statement"},
                "Net Income": {"value": 99803, "units": "USD millions", "financial_statement": "Income Statement"},
                "Operating Cash Flow": {"value": 122151, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Accounts Receivable": {"value": 28184, "units": "USD millions", "financial_statement": "Balance Sheet"},
                "Inventory": {"value": 4946, "units": "USD millions", "financial_statement": "Balance Sheet"},
                "Accounts Payable": {"value": 64115, "units": "USD millions", "financial_statement": "Balance Sheet"},
                "Depreciation & Amortization": {"value": 11104, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Capital Expenditures": {"value": 10708, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Stock-Based Compensation": {"value": 9038, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Shares Outstanding": {"value": 15943.425, "units": "millions of shares", "financial_statement": "Equity / Notes"},
                "Tax Expense": {"value": 19300, "units": "USD millions", "financial_statement": "Income Statement / Tax Note"},
                "Deferred Tax Assets": {"value": 20094, "units": "USD millions", "financial_statement": "Tax Note"},
                "Deferred Tax Liabilities": {"value": 5557, "units": "USD millions", "financial_statement": "Tax Note"},
            },
            "formula_or_rule": "Direct verified benchmark transcription; no calculation.",
            "expected_result": {
                "Revenue": 394328, "Net Income": 99803, "Operating Cash Flow": 122151,
                "Accounts Receivable": 28184, "Inventory": 4946, "Accounts Payable": 64115,
                "Depreciation & Amortization": 11104, "Capital Expenditures": 10708,
                "Stock-Based Compensation": 9038, "Shares Outstanding": 15943.425,
                "Tax Expense": 19300, "Deferred Tax Assets": 20094,
                "Deferred Tax Liabilities": 5557,
            },
        },
        2023: {
            "source": {
                "name": "Apple Form 10-K",
                "source_date": "2023-11-03",
                "provenance": "Existing Data/apple_test_dataset.py Apple benchmark",
            },
            "data": {
                "Revenue": {"value": 383285, "units": "USD millions", "financial_statement": "Income Statement"},
                "Net Income": {"value": 96995, "units": "USD millions", "financial_statement": "Income Statement"},
                "Operating Cash Flow": {"value": 110543, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Accounts Receivable": {"value": 29508, "units": "USD millions", "financial_statement": "Balance Sheet"},
                "Inventory": {"value": 6331, "units": "USD millions", "financial_statement": "Balance Sheet"},
                "Accounts Payable": {"value": 62611, "units": "USD millions", "financial_statement": "Balance Sheet"},
                "Depreciation & Amortization": {"value": 11519, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Capital Expenditures": {"value": 10959, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Stock-Based Compensation": {"value": 10833, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Shares Outstanding": {"value": 15550.061, "units": "millions of shares", "financial_statement": "Equity / Notes"},
                "Tax Expense": {"value": 16741, "units": "USD millions", "financial_statement": "Income Statement / Tax Note"},
                "Deferred Tax Assets": {"value": 24369, "units": "USD millions", "financial_statement": "Tax Note"},
                "Deferred Tax Liabilities": {"value": 7118, "units": "USD millions", "financial_statement": "Tax Note"},
            },
            "formula_or_rule": "Direct verified benchmark transcription; no calculation.",
            "expected_result": {
                "Revenue": 383285, "Net Income": 96995, "Operating Cash Flow": 110543,
                "Accounts Receivable": 29508, "Inventory": 6331, "Accounts Payable": 62611,
                "Depreciation & Amortization": 11519, "Capital Expenditures": 10959,
                "Stock-Based Compensation": 10833, "Shares Outstanding": 15550.061,
                "Tax Expense": 16741, "Deferred Tax Assets": 24369,
                "Deferred Tax Liabilities": 7118,
            },
        },
        2024: {
            "source": {
                "name": "Apple Form 10-K",
                "source_date": "2024-11-01",
                "provenance": "Existing Data/apple_test_dataset.py Apple benchmark",
            },
            "data": {
                "Revenue": {"value": 391035, "units": "USD millions", "financial_statement": "Income Statement"},
                "Net Income": {"value": 93736, "units": "USD millions", "financial_statement": "Income Statement"},
                "Operating Cash Flow": {"value": 118254, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Accounts Receivable": {"value": 33410, "units": "USD millions", "financial_statement": "Balance Sheet"},
                "Inventory": {"value": 7286, "units": "USD millions", "financial_statement": "Balance Sheet"},
                "Accounts Payable": {"value": 68960, "units": "USD millions", "financial_statement": "Balance Sheet"},
                "Depreciation & Amortization": {"value": 11445, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Capital Expenditures": {"value": 9447, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Stock-Based Compensation": {"value": 11688, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Shares Outstanding": {"value": 15116.786, "units": "millions of shares", "financial_statement": "Equity / Notes"},
                "Tax Expense": {"value": 29749, "units": "USD millions", "financial_statement": "Income Statement / Tax Note"},
                "Deferred Tax Assets": {"value": 26007, "units": "USD millions", "financial_statement": "Tax Note"},
                "Deferred Tax Liabilities": {"value": 6805, "units": "USD millions", "financial_statement": "Tax Note"},
            },
            "formula_or_rule": "Direct verified benchmark transcription; no calculation.",
            "expected_result": {
                "Revenue": 391035, "Net Income": 93736, "Operating Cash Flow": 118254,
                "Accounts Receivable": 33410, "Inventory": 7286, "Accounts Payable": 68960,
                "Depreciation & Amortization": 11445, "Capital Expenditures": 9447,
                "Stock-Based Compensation": 11688, "Shares Outstanding": 15116.786,
                "Tax Expense": 29749, "Deferred Tax Assets": 26007,
                "Deferred Tax Liabilities": 6805,
            },
        },
        2025: {
            "source": {
                "name": "Apple Form 10-K",
                "source_date": "2025-10-31",
                "provenance": "Existing Data/apple_test_dataset.py Apple benchmark",
            },
            "data": {
                "Revenue": {"value": 416161, "units": "USD millions", "financial_statement": "Income Statement"},
                "Net Income": {"value": 112010, "units": "USD millions", "financial_statement": "Income Statement"},
                "Operating Cash Flow": {"value": 111482, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Accounts Receivable": {"value": 39777, "units": "USD millions", "financial_statement": "Balance Sheet"},
                "Inventory": {"value": 5718, "units": "USD millions", "financial_statement": "Balance Sheet"},
                "Accounts Payable": {"value": 69860, "units": "USD millions", "financial_statement": "Balance Sheet"},
                "Depreciation & Amortization": {"value": 11698, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Capital Expenditures": {"value": 12715, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Stock-Based Compensation": {"value": 12863, "units": "USD millions", "financial_statement": "Cash Flow Statement"},
                "Shares Outstanding": {"value": 14773.260, "units": "millions of shares", "financial_statement": "Equity / Notes"},
                "Tax Expense": {"value": 20719, "units": "USD millions", "financial_statement": "Income Statement / Tax Note"},
                "Deferred Tax Assets": {"value": 27451, "units": "USD millions", "financial_statement": "Tax Note"},
                "Deferred Tax Liabilities": {"value": 7471, "units": "USD millions", "financial_statement": "Tax Note"},
            },
            "formula_or_rule": "Direct verified benchmark transcription; no calculation.",
            "expected_result": {
                "Revenue": 416161, "Net Income": 112010, "Operating Cash Flow": 111482,
                "Accounts Receivable": 39777, "Inventory": 5718, "Accounts Payable": 69860,
                "Depreciation & Amortization": 11698, "Capital Expenditures": 12715,
                "Stock-Based Compensation": 12863, "Shares Outstanding": 14773.260,
                "Tax Expense": 20719, "Deferred Tax Assets": 27451,
                "Deferred Tax Liabilities": 7471,
            },
        },
    },
    "calculated_financial_metrics": {
        "free_cash_flow": {
            "source": "raw_financial_data: Operating Cash Flow and Capital Expenditures",
            "data": {
                2022: {"operating_cash_flow": 122151, "capital_expenditures": 10708},
                2023: {"operating_cash_flow": 110543, "capital_expenditures": 10959},
                2024: {"operating_cash_flow": 118254, "capital_expenditures": 9447},
                2025: {"operating_cash_flow": 111482, "capital_expenditures": 12715},
            },
            "formula_or_rule": "Operating Cash Flow - Capital Expenditures",
            "expected_result": {2022: 111443, 2023: 99584, 2024: 108807, 2025: 98767},
            "units": "USD millions",
        },
        "growth_and_accrual_metrics": {
            "source": "raw_financial_data: Revenue, Net Income, Operating Cash Flow, Accounts Receivable",
            "data": {
                2023: {"current": {"revenue": 383285, "net_income": 96995, "ocf": 110543, "ar": 29508}, "previous": {"revenue": 394328, "net_income": 99803, "ocf": 122151, "ar": 28184}},
                2024: {"current": {"revenue": 391035, "net_income": 93736, "ocf": 118254, "ar": 33410}, "previous": {"revenue": 383285, "net_income": 96995, "ocf": 110543, "ar": 29508}},
                2025: {"current": {"revenue": 416161, "net_income": 112010, "ocf": 111482, "ar": 39777}, "previous": {"revenue": 391035, "net_income": 93736, "ocf": 118254, "ar": 33410}},
            },
            "formula_or_rule": {
                "growth": "(Current Year Value - Previous Year Value) / Previous Year Value",
                "ar_revenue_gap": "AR Growth - Revenue Growth",
            },
            "expected_result": {
                2023: {"revenue_growth": -0.0280046053, "net_income_growth": -0.0281354268, "ocf_growth": -0.0950299220, "ar_growth": 0.0469770082, "ar_revenue_gap": 0.0749816135},
                2024: {"revenue_growth": 0.0202199408, "net_income_growth": -0.0335996701, "ocf_growth": 0.0697556607, "ar_growth": 0.1322353260, "ar_revenue_gap": 0.1120153852},
                2025: {"revenue_growth": 0.0642551178, "net_income_growth": 0.1949517795, "ocf_growth": -0.0572665618, "ar_growth": 0.1905716851, "ar_revenue_gap": 0.1263165673},
            },
            "units": "decimal; gaps are decimal percentage-point equivalents",
        },
        "da": {
            "source": "raw_financial_data: Depreciation & Amortization and Revenue",
            "data": {
                2022: {"da": 11104, "revenue": 394328, "previous_da": None},
                2023: {"da": 11519, "revenue": 383285, "previous_da": 11104},
                2024: {"da": 11445, "revenue": 391035, "previous_da": 11519},
                2025: {"da": 11698, "revenue": 416161, "previous_da": 11445},
            },
            "formula_or_rule": {
                "growth": "(Current D&A - Previous D&A) / Previous D&A",
                "da_to_revenue": "D&A / Revenue",
            },
            "expected_result": {
                2022: {"da_growth": None, "da_to_revenue": 0.0281592989},
                2023: {"da_growth": 0.0373739193, "da_to_revenue": 0.0300533546},
                2024: {"da_growth": -0.0064241688, "da_to_revenue": 0.0292684798},
                2025: {"da_growth": 0.0221057230, "da_to_revenue": 0.0281093135},
            },
            "units": "decimal ratios",
        },
        "inventory_and_ap_growth": {
            "source": "raw_financial_data: Inventory and Accounts Payable",
            "data": {
                2023: {"inventory": 6331, "previous_inventory": 4946, "ap": 62611, "previous_ap": 64115},
                2024: {"inventory": 7286, "previous_inventory": 6331, "ap": 68960, "previous_ap": 62611},
                2025: {"inventory": 5718, "previous_inventory": 7286, "ap": 69860, "previous_ap": 68960},
            },
            "formula_or_rule": "(Current Year Value - Previous Year Value) / Previous Year Value",
            "expected_result": {
                2023: {"inventory_growth": 0.2800242620, "ap_growth": -0.0234578492},
                2024: {"inventory_growth": 0.1508450482, "ap_growth": 0.1014039067},
                2025: {"inventory_growth": -0.2152072468, "ap_growth": 0.0130510441},
            },
            "units": "decimal ratios",
        },
        "working_capital": {
            "source": "raw_financial_data: Accounts Receivable, Inventory, Accounts Payable",
            "data": {
                2023: {"ar_change": 1324, "inventory_change": 1385, "ap_change": -1504},
                2024: {"ar_change": 3902, "inventory_change": 955, "ap_change": 6349},
                2025: {"ar_change": 6367, "inventory_change": -1568, "ap_change": 900},
            },
            "formula_or_rule": "-AR Change - Inventory Change + AP Change",
            "expected_result": {
                2023: {"ar_change": 1324, "inventory_change": 1385, "ap_change": -1504, "net_working_capital_cash_effect": -4213, "classification": "Cash Use"},
                2024: {"ar_change": 3902, "inventory_change": 955, "ap_change": 6349, "net_working_capital_cash_effect": 1492, "classification": "Cash Benefit"},
                2025: {"ar_change": 6367, "inventory_change": -1568, "ap_change": 900, "net_working_capital_cash_effect": -3899, "classification": "Cash Use"},
            },
            "units": "USD millions",
        },
        "capex": {
            "source": "raw_financial_data: Capital Expenditures, Revenue, Depreciation & Amortization",
            "data": {
                2022: {"capex": 10708, "revenue": 394328, "da": 11104, "previous_capex": None},
                2023: {"capex": 10959, "revenue": 383285, "da": 11519, "previous_capex": 10708},
                2024: {"capex": 9447, "revenue": 391035, "da": 11445, "previous_capex": 10959},
                2025: {"capex": 12715, "revenue": 416161, "da": 11698, "previous_capex": 9447},
            },
            "formula_or_rule": {
                "growth": "(Current CapEx - Previous CapEx) / Previous CapEx",
                "capex_to_revenue": "CapEx / Revenue",
                "capex_to_da": "CapEx / D&A",
            },
            "expected_result": {
                2022: {"capex_growth": None, "capex_to_revenue": 0.0271550587, "capex_to_da": 0.9643371758},
                2023: {"capex_growth": 0.0234404184, "capex_to_revenue": 0.0285923008, "capex_to_da": 0.9513846688},
                2024: {"capex_growth": -0.1379687928, "capex_to_revenue": 0.0241589628, "capex_to_da": 0.8254259502},
                2025: {"capex_growth": 0.3459299248, "capex_to_revenue": 0.0305530792, "capex_to_da": 1.0869379381},
            },
            "units": "decimal ratios",
        },
        "sbc_and_shares": {
            "source": {
                "core": "raw_financial_data: Stock-Based Compensation, Net Income, Revenue, OCF, Shares Outstanding",
                "supplemental": "Verified Apple Form 10-K inputs preserved in Analysis/buyback_adjustment.py",
            },
            "data": {
                2022: {"sbc": 9038, "net_income": 99803, "revenue": 394328, "ocf": 122151, "shares": 15943.425, "previous_shares": None, "shares_issued_net": 85.228, "shares_repurchased": 568.589, "cash_spent_on_buybacks": 89402},
                2023: {"sbc": 10833, "net_income": 96995, "revenue": 383285, "ocf": 110543, "shares": 15550.061, "previous_shares": 15943.425, "shares_issued_net": 78.055, "shares_repurchased": 471.419, "cash_spent_on_buybacks": 77550},
                2024: {"sbc": 11688, "net_income": 93736, "revenue": 391035, "ocf": 118254, "shares": 15116.786, "previous_shares": 15550.061, "shares_issued_net": 66.097, "shares_repurchased": 499.372, "cash_spent_on_buybacks": 94949},
                2025: {"sbc": 12863, "net_income": 112010, "revenue": 416161, "ocf": 111482, "shares": 14773.260, "previous_shares": 15116.786, "shares_issued_net": 58.146, "shares_repurchased": 401.672, "cash_spent_on_buybacks": 90711},
            },
            "formula_or_rule": {
                "sbc_ratios": "SBC / denominator shown (Net Income uses absolute value in the red-flag rule)",
                "share_growth": "(Current Shares - Previous Shares) / Previous Shares",
                "net_share_effect": "Shares Issued Net - Shares Repurchased",
                "buyback_offset_ratio": "Shares Repurchased / Shares Issued Net",
            },
            "expected_result": {
                2022: {"sbc_to_revenue": 0.0229200057, "sbc_to_ocf": 0.0739903889, "sbc_to_net_income": 0.0905584000, "shares_growth": None, "net_share_effect": -483.361, "buyback_offset_ratio": 6.6713873375},
                2023: {"sbc_to_revenue": 0.0282635637, "sbc_to_ocf": 0.0979980641, "sbc_to_net_income": 0.1116861694, "shares_growth": -0.0246724904, "net_share_effect": -393.364, "buyback_offset_ratio": 6.0395746589},
                2024: {"sbc_to_revenue": 0.0298899076, "sbc_to_ocf": 0.0988380943, "sbc_to_net_income": 0.1246906205, "shares_growth": -0.0278632347, "net_share_effect": -433.275, "buyback_offset_ratio": 7.5551386598},
                2025: {"sbc_to_revenue": 0.0309087108, "sbc_to_ocf": 0.1153818554, "sbc_to_net_income": 0.1148379609, "shares_growth": -0.0227248041, "net_share_effect": -343.526, "buyback_offset_ratio": 6.9079902315},
            },
            "units": "decimal ratios; share values in millions; cash in USD millions",
        },
        "deferred_taxes": {
            "source": "raw_financial_data: Deferred Tax Assets, Deferred Tax Liabilities, Net Income",
            "data": {
                2022: {"dta": 20094, "dtl": 5557, "net_income": 99803, "previous_dta": None, "previous_dtl": None},
                2023: {"dta": 24369, "dtl": 7118, "net_income": 96995, "previous_dta": 20094, "previous_dtl": 5557},
                2024: {"dta": 26007, "dtl": 6805, "net_income": 93736, "previous_dta": 24369, "previous_dtl": 7118},
                2025: {"dta": 27451, "dtl": 7471, "net_income": 112010, "previous_dta": 26007, "previous_dtl": 6805},
            },
            "formula_or_rule": {
                "dta_to_net_income": "DTA / abs(Net Income)",
                "growth": "(Current Value - Previous Value) / abs(Previous Value)",
            },
            "expected_result": {
                2022: {"dta_to_net_income": 0.2013366332, "dta_growth": None, "dtl_growth": None},
                2023: {"dta_to_net_income": 0.2512397546, "dta_growth": 0.2127500746, "dtl_growth": 0.2809069642},
                2024: {"dta_to_net_income": 0.2774494324, "dta_growth": 0.0672165456, "dtl_growth": -0.0439730261},
                2025: {"dta_to_net_income": 0.2450763325, "dta_growth": 0.0555235129, "dtl_growth": 0.0978692138},
            },
            "units": "decimal ratios",
        },
    },
    "red_flag_results": {
        "accrual_quality": {
            "source": "calculated_financial_metrics.growth_and_accrual_metrics",
            "data": {
                2023: {"ar_growth": 0.0469770082, "revenue_growth": -0.0280046053, "ar_revenue_gap": 0.0749816135, "net_income_growth": -0.0281354268, "ocf_growth": -0.0950299220},
                2024: {"ar_growth": 0.1322353260, "revenue_growth": 0.0202199408, "ar_revenue_gap": 0.1120153852, "net_income_growth": -0.0335996701, "ocf_growth": 0.0697556607},
                2025: {"ar_growth": 0.1905716851, "revenue_growth": 0.0642551178, "ar_revenue_gap": 0.1263165673, "net_income_growth": 0.1949517795, "ocf_growth": -0.0572665618},
            },
            "formula_or_rule": {
                "ar": "AR Growth - Revenue Growth >= 10 percentage points",
                "ni_ocf": "Net Income Growth > 0 AND OCF Growth < 0",
                "combined": "AR Flag AND NI OCF Flag",
            },
            "expected_result": {
                2023: {"ar_flag": False, "ni_ocf_flag": False, "combined_accrual_flag": False, "signal": "No accrual warning", "severity": "None"},
                2024: {"ar_flag": True, "ni_ocf_flag": False, "combined_accrual_flag": False, "signal": "Accrual warning", "severity": "Medium"},
                2025: {"ar_flag": True, "ni_ocf_flag": True, "combined_accrual_flag": True, "signal": "Strong accrual warning", "severity": "High"},
            },
        },
        "working_capital": {
            "source": "calculated_financial_metrics.working_capital plus growth metrics",
            "data": {
                2023: {"inventory_growth": 0.2800242620, "revenue_growth": -0.0280046053, "ap_growth": -0.0234578492, "ocf_growth": -0.0950299220, "net_cash_effect": -4213},
                2024: {"inventory_growth": 0.1508450482, "revenue_growth": 0.0202199408, "ap_growth": 0.1014039067, "ocf_growth": 0.0697556607, "net_cash_effect": 1492},
                2025: {"inventory_growth": -0.2152072468, "revenue_growth": 0.0642551178, "ap_growth": 0.0130510441, "ocf_growth": -0.0572665618, "net_cash_effect": -3899},
            },
            "formula_or_rule": {
                "inventory": "Inventory Growth - Revenue Growth >= 10 percentage points",
                "ap_payment_pressure": "AP Growth - Revenue Growth >= 10 percentage points AND OCF Growth < 0",
                "ap_supplier_financing": "AP Growth > Revenue Growth AND OCF Growth >= 0",
                "cash_use": "Net Working-Capital Cash Effect < 0",
            },
            "expected_result": {
                2023: {"inventory_flag": True, "ap_classification": "No AP concern triggered", "working_capital_cash_use": True, "overall_severity": "Medium"},
                2024: {"inventory_flag": True, "ap_classification": "Normal supplier financing pattern", "working_capital_cash_use": False, "overall_severity": "Medium"},
                2025: {"inventory_flag": False, "ap_classification": "No AP concern triggered", "working_capital_cash_use": True, "overall_severity": "Low"},
            },
        },
        "capex": {
            "source": "calculated_financial_metrics.capex",
            "data": {
                2022: {"capex_to_da": 0.9643371758}, 2023: {"capex_to_da": 0.9513846688},
                2024: {"capex_to_da": 0.8254259502}, 2025: {"capex_to_da": 1.0869379381},
            },
            "formula_or_rule": "CapEx / D&A >= 1.20x",
            "expected_result": {
                2022: {"status": "No investigation triggered", "flag": False, "severity": "None"},
                2023: {"status": "No investigation triggered", "flag": False, "severity": "None"},
                2024: {"status": "No investigation triggered", "flag": False, "severity": "None"},
                2025: {"status": "No investigation triggered", "flag": False, "severity": "None"},
            },
        },
        "deferred_taxes": {
            "source": "calculated_financial_metrics.deferred_taxes and growth_and_accrual_metrics",
            "data": {
                2023: {"dta_to_net_income": 0.2512397546, "net_income_growth": -0.0281354268, "net_income": 96995, "dta_growth": 0.2127500746, "dtl_growth": 0.2809069642},
                2024: {"dta_to_net_income": 0.2774494324, "net_income_growth": -0.0335996701, "net_income": 93736, "dta_growth": 0.0672165456, "dtl_growth": -0.0439730261},
                2025: {"dta_to_net_income": 0.2450763325, "net_income_growth": 0.1949517795, "net_income": 112010, "dta_growth": 0.0555235129, "dtl_growth": 0.0978692138},
            },
            "formula_or_rule": {
                "dta_risk": "DTA / |Net Income| >= 50% AND (NI Growth <= -10% OR Net Income <= 0)",
                "movement": "abs(DTA Growth) >= 25% OR abs(DTL Growth) >= 25%",
            },
            "expected_result": {
                2023: {"dta_risk_flag": False, "deferred_tax_movement_flag": True, "movement_classification": "Large DTL movement", "overall_tax_severity": "Medium"},
                2024: {"dta_risk_flag": False, "deferred_tax_movement_flag": False, "movement_classification": "No unusual deferred-tax movement", "overall_tax_severity": "None"},
                2025: {"dta_risk_flag": False, "deferred_tax_movement_flag": False, "movement_classification": "No unusual deferred-tax movement", "overall_tax_severity": "None"},
            },
        },
        "sbc": {
            "source": "calculated_financial_metrics.sbc_and_shares",
            "data": {
                2022: {"sbc_to_net_income": 0.0905584000, "shares_growth": None, "buyback_offset_ratio": 6.6713873375},
                2023: {"sbc_to_net_income": 0.1116861694, "shares_growth": -0.0246724904, "buyback_offset_ratio": 6.0395746589},
                2024: {"sbc_to_net_income": 0.1246906205, "shares_growth": -0.0278632347, "buyback_offset_ratio": 7.5551386598},
                2025: {"sbc_to_net_income": 0.1148379609, "shares_growth": -0.0227248041, "buyback_offset_ratio": 6.9079902315},
            },
            "formula_or_rule": {
                "large_sbc": "SBC / abs(Net Income) >= 10%",
                "dilution": "Shares Outstanding Growth >= 1%",
                "buyback_offset": "Shares Issued Net > 0 AND Shares Repurchased >= Shares Issued Net",
            },
            "expected_result": {
                2022: {"large_sbc_flag": False, "dilution_flag": False, "buyback_offset_classification": "Buybacks more than offset share issuance", "overall_sbc_severity": "Low"},
                2023: {"large_sbc_flag": True, "dilution_flag": False, "buyback_offset_classification": "Buybacks more than offset share issuance", "overall_sbc_severity": "Medium"},
                2024: {"large_sbc_flag": True, "dilution_flag": False, "buyback_offset_classification": "Buybacks more than offset share issuance", "overall_sbc_severity": "Medium"},
                2025: {"large_sbc_flag": True, "dilution_flag": False, "buyback_offset_classification": "Buybacks more than offset share issuance", "overall_sbc_severity": "Medium"},
            },
        },
        "overall_severity": {
            "source": "Existing Analysis/severity_system.py output from consolidated red flags",
            "data": {
                2023: {"triggered_metrics": ["Inventory growth vs Revenue growth"]},
                2024: {"triggered_metrics": ["AR growth vs Revenue growth", "Inventory growth vs Revenue growth", "Accounts Payable pattern"]},
                2025: {"triggered_metrics": ["AR growth vs Revenue growth", "Net Income growth vs OCF growth"]},
            },
            "formula_or_rule": "Preserve the existing severity mapping and highest existing fiscal-year severity; no score.",
            "expected_result": {
                2023: {"high_level_severity": "Needs Investigation", "material_concern_count": 0, "needs_investigation_count": 1, "low_risk_count": 7},
                2024: {"high_level_severity": "Needs Investigation", "material_concern_count": 0, "needs_investigation_count": 3, "low_risk_count": 5},
                2025: {"high_level_severity": "Material Concern", "material_concern_count": 2, "needs_investigation_count": 0, "low_risk_count": 6},
                "benchmark": {"severity": "Material Concern", "explanation": "At least one analyzed fiscal year contains stronger combined earnings-quality signals under the existing predefined rules; heightened analyst investigation is required."},
            },
        },
    },
    "normalized_earnings_results": {
        "source": {
            "reported_net_income": "raw_financial_data: Net Income",
            "one_off_item": "Apple Form 10-K dated 2024-11-01, Note 7 - Income Taxes",
            "provenance": "Existing Data/one_off_items.py manual benchmark",
        },
        "data": {
            2022: {"reported_net_income": 99803, "net_normalization_adjustment": 0, "one_off_categories": "None"},
            2023: {"reported_net_income": 96995, "net_normalization_adjustment": 0, "one_off_categories": "None"},
            2024: {"reported_net_income": 93736, "net_normalization_adjustment": 10200, "one_off_categories": "Unusual tax gains/losses", "description": "One-time income tax charge related to the European Commission State Aid Decision", "direction": "Charge", "tax_basis": "Tax item", "manual_classification": "Non-recurring", "manual_review_status": "Reviewed", "adjustment_status": "Adjusted"},
            2025: {"reported_net_income": 112010, "net_normalization_adjustment": 0, "one_off_categories": "None"},
        },
        "formula_or_rule": {
            "normalized_net_income": "Reported Net Income + Net Normalization Adjustment",
            "difference": "Normalized Net Income - Reported Net Income",
            "difference_percentage": "Difference / abs(Reported Net Income)",
            "large_difference": "abs(Percentage Difference) >= 10%",
            "repeated_one_off": "Years Appearing >= 2",
            "eligible_adjustment": "Manually Non-recurring After-tax or Tax item; Charge added back, Gain removed",
        },
        "expected_result": {
            2022: {"normalized_net_income": 99803, "difference": 0, "percentage_difference": 0.0, "large_difference_flag": False, "repeated_one_off_flag": False, "overall_severity": "None"},
            2023: {"normalized_net_income": 96995, "difference": 0, "percentage_difference": 0.0, "large_difference_flag": False, "repeated_one_off_flag": False, "overall_severity": "None"},
            2024: {"normalized_net_income": 103936, "difference": 10200, "percentage_difference": 0.1088162499, "large_difference_flag": True, "repeated_one_off_flag": False, "normalization_signal": "Normalization requires investigation", "overall_severity": "Medium"},
            2025: {"normalized_net_income": 112010, "difference": 0, "percentage_difference": 0.0, "large_difference_flag": False, "repeated_one_off_flag": False, "overall_severity": "None"},
        },
    },
}
