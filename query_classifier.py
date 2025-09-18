import google.generativeai as genai
from typing import Dict, Tuple

class QueryClassifier:
    def __init__(self, api_key: str):
        self.api_key = api_key
        genai.configure(api_key=self.api_key)

    def get_classification_prompt(self, query: str) -> str:
        return f"""Classify this query into one of these categories:
1. WALLET_API - For queries about user's personal wallet, deposits, withdrawals
2. TRADING_API - For queries about user's personal trading history, orders, prices
3. FAQ_DB - For general questions about platform features or documentation

Query: "{query}"

Respond in this exact format:
CATEGORY: [category name]
PARAMS: [if WALLET_API: type=deposit/withdrawal, if TRADING_API: symbol=BTC-INR/ETH-INR if mentioned]"""

    def classify_query(self, query: str) -> Tuple[str, Dict]:
        """Use LLM to classify the query and extract parameters."""
        try:
            # Get classification from LLM
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(self.get_classification_prompt(query))
            
            # Parse response
            lines = response.text.strip().split('\n')
            result = {}
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    result[key.strip()] = value.strip()
            
            # Extract category and parameters
            category = result.get('CATEGORY', 'FAQ_DB')
            
            # Parse parameters if present
            params = {}
            if 'PARAMS' in result:
                param_str = result['PARAMS'].strip('[]').strip()
                if param_str and param_str.lower() != 'none':
                    for param in param_str.split(','):
                        if '=' in param:
                            key, value = param.split('=')
                            params[key.strip()] = value.strip()
            
            return category, params
            
        except Exception as e:
            print(f"Error in query classification: {str(e)}")
            return 'FAQ_DB', {}