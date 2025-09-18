import os
import json
import time
import google.generativeai as genai
from typing import Optional, Dict, Any
from query_classifier import QueryClassifier
from api_client_v2 import CSProAPIClient

class BotFacade:
    def __init__(self, auth_token: str, api_key: str = "AIzaSyCfaXQtJEm86EO90--ssZwh5motDQ-Cpm0"):
        self.api_key = api_key
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.query_classifier = QueryClassifier(self.api_key)
        self.api_client = CSProAPIClient(auth_token)
        
        # Load fees data
        try:
            with open('raw_data/fees_data.json', 'r') as f:
                self.fees_data = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load fees data: {str(e)}")
            self.fees_data = {}

    def get_fees_data(self, params: Dict[str, Any]) -> str:
        """Get fees information based on parameters."""
        try:
            market = params.get('market', 'spot')
            currency = params.get('currency')
            fee_type = params.get('fee_type', 'all')
            
            if market not in self.fees_data:
                return f"Fee information for {market} market is not available."

            # Get relevant fee data
            fee_info = {}
            if market == 'spot':
                fee_info = {"spot": self.fees_data[market]}
            elif market == 'futures':
                if currency:
                    fee_info = {"futures": {currency: self.fees_data[market][currency]}}
                else:
                    fee_info = {"futures": self.fees_data[market]}
            elif market == 'options':
                if currency:
                    fee_info = {"options": {currency: self.fees_data[market][currency]}}
                else:
                    fee_info = {"options": self.fees_data[market]}

            # Use LLM to generate response
            prompt = f"""Based on this fee data, answer the user's question about {market} trading fees.
If specific fee type (maker/taker) is asked, focus on that.

Fee Data:
{json.dumps(fee_info, indent=2)}

Generate a clear, concise response focusing on the fees structure:"""

            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            print(f"Error getting fees data: {str(e)}")
            return "Sorry, there was an error retrieving the fee information."

    def get_data_from_llm(self, model, collection, query: str) -> str:
        """Get data from appropriate source based on query classification."""
        try:
            # Classify the query
            classification = self.query_classifier.classify_query(query)
            category = classification.get("category", "FAQ_DB")
            params = classification.get("params", {})
            
            # Handle based on classification
            if category == "WALLET_API":
                return self.api_client.analyze_transactions(params.get("type", "all"))
            elif category == "TRADING_API":
                trading_data = self.api_client.analyze_trading_history(params.get("symbol"))
                
                # Pass trading data to LLM for natural language response
                prompt = f"""Based on this trading data, answer the user's question: "{query}"

Trading Data:
{json.dumps(trading_data, indent=2)}

Generate a natural language response:"""
                
                response = self.model.generate_content(prompt)
                return response.text
                
            elif category == "FEES_DATA":
                return self.get_fees_data(params)
            else:  # FAQ_DB
                results = collection.query(
                    query_texts=[query],
                    n_results=2
                )
                
                if not results or not results['documents']:
                    return "I couldn't find any relevant information in the FAQ database."
                    
                # Pass results to LLM for better response
                docs = results['documents'][0]
                prompt = f"""Based on these relevant documents, answer the user's question: "{query}"

Relevant Information:
{' '.join(docs)}

Generate a natural language response:"""
                
                response = self.model.generate_content(prompt)
                return response.text
                
        except Exception as e:
            print(f"Error in get_data_from_llm: {str(e)}")
            return f"Error: {str(e)}"