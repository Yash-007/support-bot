import os
import json
import time
import requests
import google.generativeai as genai
from typing import Optional, Dict, Any
from query_classifier import QueryClassifier
from api_client_v2 import CSProAPIClient

class BotFacade:
    def __init__(self, auth_token: str, api_key: str = "AIzaSyA6RU0_ETYrYY8YwS1xZQ_2MoL8apOIWyA"):
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

            try:
                response = self.model.generate_content(prompt)
                return response.text if response else "Sorry, couldn't generate a response for fee data."
            except Exception as e:
                print(f"Error generating fee response: {str(e)}")
                return "Sorry, there was an error processing the fee information."
            
        except Exception as e:
            print(f"Error getting fees data: {str(e)}")
            return "Sorry, there was an error retrieving the fee information."

    def is_crypto_related(self, query: str) -> bool:
        """Verify if the query is related to cryptocurrency."""
        try:
            prompt = f"""Determine if the following query is related to cryptocurrency, blockchain, or digital assets.

Query: "{query}"

Respond with only "YES" if the query is crypto-related, or "NO" if it's not crypto-related.

Examples of crypto-related queries:
- Bitcoin price, Ethereum news, crypto trading
- Blockchain technology, DeFi, NFTs
- Cryptocurrency market, digital assets
- Crypto wallets, mining, staking

Examples of non-crypto queries:
- Weather, sports, general news
- Cooking recipes, travel information
- Non-crypto financial topics

Response:"""

            response = self.model.generate_content(prompt)
            if response and response.text:
                result = response.text.strip().upper()
                return result == "YES"
            return False
            
        except Exception as e:
            print(f"Error verifying crypto relation: {str(e)}")
            return False

    def perform_web_search(self, query: str) -> str:
        """Perform web search for crypto-related queries using LLM directly."""
        try:
            print("Performing web search using LLM")
            
            # Use LLM directly to answer crypto-related queries
            prompt = f"""Answer this cryptocurrency-related question: "{query}"

Please provide a comprehensive, accurate response that:
1. Directly answers the user's question
2. Is specific to cryptocurrency/crypto topics
3. Includes relevant details and context
4. Maintains a helpful, informative tone
5. If you don't have the most current information, mention that the data might be outdated
6. Suggest checking current sources for the latest information

Response:"""
            
            response = self.model.generate_content(prompt)
            return response.text if response else "Sorry, I couldn't generate a response for that crypto topic."
            
        except Exception as e:
            print(f"Error in web search: {str(e)}")
            return "Sorry, there was an error processing your crypto query."

    def get_data_from_llm(self, model, collection, query: str, web: bool = False) -> str:
        """Get data from appropriate source based on query classification."""
        try:
            # If web search is requested, first verify if query is crypto-related
            if web:
                if not self.is_crypto_related(query):
                    return "I can only search for cryptocurrency-related topics. Please ask about crypto, blockchain, or digital assets."
                return self.perform_web_search(query)
            
            # Classify the query
            classification = self.query_classifier.classify_query(query)
            if not classification:
                return "Sorry, I couldn't understand your query. Please try rephrasing it."

            category = classification.get("category", "FAQ_DB")
            params = classification.get("params", {})
            
            # Handle based on classification
            if category == "WALLET_API":
                try:
                    wallet_data = self.api_client.analyze_transactions(params.get("type", "all"))
                    if not wallet_data or "error" in wallet_data:
                        return "Sorry, I couldn't retrieve your wallet data at this time."
                    
                    # Pass wallet data to LLM for natural language response
                    prompt = f"""Based on this wallet transaction data, answer the user's question: "{query}"

Wallet Data:
{json.dumps(wallet_data, indent=2)}

Generate a natural, conversational response that includes:
1. Direct answers to the specific question
2. Relevant transaction details (amounts, dates, sources)
3. Any notable patterns or summaries if relevant
4. Format numbers clearly with proper currency symbols (₹ for INR)

Response:"""
                    
                    response = self.model.generate_content(prompt)
                    return response.text if response else "Sorry, couldn't analyze the wallet data."
                except Exception as e:
                    print(f"Error processing wallet data: {str(e)}")
                    return "Sorry, there was an error processing your wallet information."

            elif category == "TRADING_API":
                try:
                    trading_data = self.api_client.analyze_trading_history(params.get("symbol"))
                    if not trading_data or "error" in trading_data:
                        return "Sorry, I couldn't retrieve your trading data at this time."
                    
                    # Pass trading data to LLM for natural language response
                    prompt = f"""Based on this trading data, answer the user's question: "{query}"

Trading Data:
{json.dumps(trading_data, indent=2)}

Generate a natural language response that includes:
1. Direct answers to the specific question
2. Relevant trade details (prices, volumes, dates)
3. Any notable patterns or statistics
4. Format numbers clearly with proper currency symbols (₹ for INR)

Response:"""
                    
                    response = self.model.generate_content(prompt)
                    return response.text if response else "Sorry, couldn't analyze the trading data."
                except Exception as e:
                    print(f"Error processing trading data: {str(e)}")
                    return "Sorry, there was an error processing your trading information."

            elif category == "PORTFOLIO_API":
                try:
                    portfolio_data = self.api_client.analyze_portfolio(params.get("currency"))
                    if not portfolio_data or "error" in portfolio_data:
                        return "Sorry, I couldn't retrieve your portfolio data at this time."
                    
                    # Pass portfolio data to LLM for natural language response
                    prompt = f"""Based on this portfolio data, answer the user's question: "{query}"

Portfolio Data:
{json.dumps(portfolio_data, indent=2)}

Generate a natural language response that includes:
1. Direct answers to the specific question
2. Relevant portfolio details (values, P&L, holdings)
3. Any notable patterns or insights
4. Format numbers clearly with proper currency symbols (₹ for INR)
5. Include percentages for P&L where relevant

Response:"""
                    
                    response = self.model.generate_content(prompt)
                    return response.text if response else "Sorry, couldn't analyze the portfolio data."
                except Exception as e:
                    print(f"Error processing portfolio data: {str(e)}")
                    return "Sorry, there was an error processing your portfolio information."
                
            elif category == "FEES_DATA":
                return self.get_fees_data(params)
            else:  # FAQ_DB
                try:
                    results = collection.query(
                        query_texts=[query],
                        n_results=2
                    )
                    
                    if not results or not results.get('documents'):
                        return "I couldn't find any relevant information in the FAQ database."
                        
                    # Pass results to LLM for better response
                    docs = results['documents'][0]
                    prompt = f"""Based on these relevant documents, answer the user's question: "{query}"

Relevant Information:
{' '.join(docs)}

Generate a natural, helpful response that:
1. Directly addresses the user's question
2. Includes relevant details from the documents
3. Uses a conversational tone
4. Formats any technical information clearly

Response:"""
                    
                    response = self.model.generate_content(prompt)
                    return response.text if response else "Sorry, couldn't generate a response from the FAQ data."
                except Exception as e:
                    print(f"Error processing FAQ data: {str(e)}")
                    return "Sorry, there was an error processing the FAQ information."
                
        except Exception as e:
            print(f"Error in get_data_from_llm: {str(e)}")
            return "I encountered an error while processing your request. Please try again."