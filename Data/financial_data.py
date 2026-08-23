import pandas as pd


required_fields = [
    "Company",
    "Ticker",
    "Fiscal Year",
    "Metric",
    "Value",
    "Units",
    "Financial Statement",
    "Source",
    "Source Date",
]

financial_data = [
    {
        "Company": "Test Company",
        "Ticker": "TEST",
        "Fiscal Year": 2024,
        "Metric": "Revenue",
        "Value": 1250.0,
        "Units": "USD millions",
        "Financial Statement": "Income Statement",
        "Source": "Sample Data",
        "Source Date": "2025-02-15",
    },
    {
        "Company": "Test Company",
        "Ticker": "TEST",
        "Fiscal Year": 2024,
        "Metric": "Net Income",
        "Value": 145.0,
        "Units": "USD millions",
        "Financial Statement": "Income Statement",
        "Source": "Sample Data",
        "Source Date": "2025-02-15",
    },
    {
        "Company": "Test Company",
        "Ticker": "TEST",
        "Fiscal Year": 2024,
        "Metric": "Operating Cash Flow",
        "Value": 190.0,
        "Units": "USD millions",
        "Financial Statement": "Cash Flow Statement",
        "Source": "Sample Data",
        "Source Date": "2025-02-15",
    },
    {
        "Company": "Test Company",
        "Ticker": "TEST",
        "Fiscal Year": 2025,
        "Metric": "Revenue",
        "Value": 1380.0,
        "Units": "USD millions",
        "Financial Statement": "Income Statement",
        "Source": "Sample Data",
        "Source Date": "2026-02-16",
    },
    {
        "Company": "Test Company",
        "Ticker": "TEST",
        "Fiscal Year": 2025,
        "Metric": "Net Income",
        "Value": 162.0,
        "Units": "USD millions",
        "Financial Statement": "Income Statement",
        "Source": "Sample Data",
        "Source Date": "2026-02-16",
    },
    {
        "Company": "Test Company",
        "Ticker": "TEST",
        "Fiscal Year": 2025,
        "Metric": "Operating Cash Flow",
        "Value": 215.0,
        "Units": "USD millions",
        "Financial Statement": "Cash Flow Statement",
        "Source": "Sample Data",
        "Source Date": "2026-02-16",
    },
]

financial_data_df = pd.DataFrame(financial_data)

print(financial_data_df)
print(financial_data_df.columns.tolist())

missing_fields = [
    field for field in required_fields if field not in financial_data_df.columns
]

if missing_fields:
    for field in missing_fields:
        print(f"Missing required field: {field}")
else:
    print("Financial data structure validated successfully")
