import json
import os
from api_client import APIClient

# Initialize empty lists/dicts in case of errors
FAQ_DOCS = []
smart_invest_profits = {}

try:
    smart_invest_profits = APIClient.get_smart_invest_data()
except Exception as e:
    print(f"Warning: Failed to get smart investment data: {str(e)}")
    smart_invest_profits = {"error": "Data temporarily unavailable"}

# Load FAQ data
try:
    faq_path = os.path.join(os.path.dirname(__file__), '..', 'faq_data.json')
    with open(faq_path, 'r') as f:
        faq_data = json.load(f)

    # Convert FAQ data to documents
    for faq in faq_data:
        try:
            # Validate required fields
            required_fields = ['title', 'content', 'category', 'subcategory', 'type', 'keywords']
            if not all(field in faq for field in required_fields):
                print(f"Warning: Skipping FAQ entry due to missing fields: {faq.get('id', 'unknown')}")
                continue

            # Create a structured document with metadata
            doc = f"""Question: {faq['title']}
Answer: {faq['content']}
Category: {faq['category']}
Subcategory: {faq['subcategory']}
Type: {faq['type']}
Keywords: {', '.join(faq['keywords'])}"""
            FAQ_DOCS.append(doc)
        except Exception as e:
            print(f"Warning: Failed to process FAQ entry: {str(e)}")
            continue

except Exception as e:
    print(f"Error: Failed to load FAQ data: {str(e)}")
    # Add a default FAQ doc so the system can still run
    FAQ_DOCS = ["Default FAQ content available when system is back online."]

INITIAL_DOCS = [
    "You can deposit funds via bank transfer.",
    "Our futures trading fees are 0.02% for takers and 0.01% for makers.",
    "Withdrawals are processed within 24 hours.",
    "We have Smart invest for automated trading.",
    "2025-09-15 BTC-USD BUY qty:0.1 fee:0.0005 pnl:-2.3, 2025-09-14 ETH-USD SELL qty:1.0 fee:0.002 pnl:5.2"
]


KYC_DOC = """
The valid KYC documents that you will need to complete your KYC verification process on CoinSwitch PRO are: 
1. PAN card for ID proof, 
2. Any one of the documents below for address proof
Aadhaar,Voter ID, Passport, 
"""


KYC_INSTRUCTIONS = """
You have to upload both front and backside photos of the documents,
Both PAN and Aadhaar/Voter ID/passport should belong to you,
Driving license will not be accepted.
"""

# TRADING_STRATEGIES = ['Trading types in coinswitch : API_TRADING (SPOT+FUTURES), SMART_INVEST (AUTOMATED TRADING), '
# 'FUTURES_TRADING (MARGIN), OPTIONS_TRADING']

FINAL_DOCS = INITIAL_DOCS + [KYC_DOC, KYC_INSTRUCTIONS] + [f"Smart Invest historical profits: {smart_invest_profits}"] + FAQ_DOCS

