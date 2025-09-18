import json
import google.generativeai as genai
from typing import Dict, Any

class QueryClassifier:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
    def classify_query(self, query: str) -> Dict[str, Any]:
        """Classify the query to determine the appropriate data source and parameters."""
        
        prompt = f"""Classify the following query into one of these categories:
- WALLET_API: For queries about wallet transactions, deposits, withdrawals
- TRADING_API: For queries about trading history, orders, positions
- FEES_DATA: For queries about trading fees, commission rates, fee tiers
- FAQ_DB: For general questions about the platform

Output should be valid JSON with this structure:
{{
    "category": "WALLET_API|TRADING_API|FEES_DATA|FAQ_DB",
    "params": {{
        // For WALLET_API:
        "type": "deposit|withdrawal|all",  // Transaction type
        "status": "success|pending|failed|all"  // Transaction status
        
        // For TRADING_API:
        "type": "buy|sell|all",  // Order type
        "symbol": "btc|eth|etc",  // Cryptocurrency symbol (null if not specified)
        "status": "completed|cancelled|all"  // Order status
        
        // For FEES_DATA:
        "market": "spot|futures|options",  // Market type
        "currency": "inr|usdt",  // Fee currency (for futures/options)
        "fee_type": "maker|taker|all"  // Fee type
    }}
}}

Query: {query}

Response (in JSON):"""

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Extract JSON from response if it's wrapped in backticks
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0]
                
            print("\nRaw classification response:", response_text)
            
            # Parse and validate JSON response
            classification = json.loads(response_text)
            print("Cleaned classification:", json.dumps(classification, indent=2))
            
            # Validate required fields
            if "category" not in classification:
                raise ValueError("Missing 'category' in classification")
            if "params" not in classification:
                classification["params"] = {}
                
            print(f"Query classified as: {classification['category']}")
            print(f"Parameters: {classification['params']}")
            
            return classification
            
        except Exception as e:
            print(f"\nError in query classification: {str(e)}")
            # Return a default classification to FAQ_DB on error
            return {
                "category": "FAQ_DB",
                "params": {}
            }