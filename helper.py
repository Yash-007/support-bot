import google.generativeai as genai
import time
from api_client_v2 import CSProAPIClient
from query_classifier import QueryClassifier

class BotFacade:
    def __init__(self, auth_token: str):
        # Initialize Gemini
        self.api_key = "AIzaSyCfaXQtJEm86EO90--ssZwh5motDQ-Cpm0"
        try:
            genai.configure(api_key=self.api_key)
        except Exception as e:
            print(f"Warning: Failed to configure Gemini API: {str(e)}")
            
        # Initialize components
        self.query_classifier = QueryClassifier(api_key=self.api_key)
        self.api_client = CSProAPIClient(auth_token=auth_token)
        self.auth_token = auth_token

    def build_prompt(self, query: str, contexts: list, user_trades: list = None) -> str:
        """Build a prompt for the LLM using the provided context and query.
        
        Args:
            query: The user's question
            contexts: List of relevant documents/contexts
            user_trades: Optional list of trade data
            
        Returns:
            Formatted prompt string
        """
        try:
            ctx_parts = []
            
            # Validate inputs
            if not isinstance(query, str) or not query.strip():
                raise ValueError("Query must be a non-empty string")
            if not isinstance(contexts, list):
                raise ValueError("Contexts must be a list")
            
            # Format user trades
            if user_trades:
                try:
                    trades_text = "\n".join(
                        f"{i+1}. {t['date']} {t['symbol']} {t['side']} qty:{t['qty']} fee:{t['fee']} pnl:{t['pnl']}" 
                        for i, t in enumerate(user_trades)
                    )
                    ctx_parts.append(f"USER_TRADES:\n{trades_text}")
                except (KeyError, TypeError) as e:
                    print(f"Warning: Invalid trade data format: {str(e)}")
            
            # Format FAQ / static docs
            if contexts:
                try:
                    # Handle both single strings and lists in contexts
                    if isinstance(contexts[0], list):
                        docs_text = "\n".join(f"{i+1}. {str(c)}" for i, c in enumerate(contexts[0]))
                    else:
                        docs_text = "\n".join(f"{i+1}. {str(c)}" for i, c in enumerate(contexts))
                    ctx_parts.append(f"FAQ_DOCS:\n{docs_text}")
                except Exception as e:
                    print(f"Warning: Error formatting contexts: {str(e)}")
                    # Fallback formatting
                    docs_text = "\n".join(str(c) for c in contexts)
                    ctx_parts.append(f"FAQ_DOCS:\n{docs_text}")
            
            ctx_text = "\n\n".join(ctx_parts) if ctx_parts else "No context available."
            
            # Build the final prompt
            prompt = (
                "You are an expert advisor for a trading platform. "
                "Provide accurate information based STRICTLY on the context provided below. "
                "Follow these guidelines:\n"
                "1. Use ONLY information from the provided context\n"
                "2. Be precise with any numbers, dates, or specific details\n"
                "3. Present information in a clear, organized manner\n"
                "4. Use bullet points when listing multiple items\n"
                "5. If information is not in the context, state: 'I don't have information about that specific aspect'\n\n"
                f"CONTEXT:\n{ctx_text}\n\n"
                f"QUESTION:\n{query}\n\nAnswer:"
            )
            
            return prompt
            
        except Exception as e:
            print(f"Error building prompt: {str(e)}")
            return f"Error: Failed to build prompt - {str(e)}"
    
    def call_gemini(self, prompt: str) -> str:
        """Call the Gemini API with error handling and retries.
        
        Args:
            prompt: The formatted prompt to send to Gemini
            
        Returns:
            The model's response text
        """
        if not isinstance(prompt, str) or not prompt.strip():
            return "Error: Invalid prompt"

        max_retries = 3
        base_delay = 1

        for attempt in range(max_retries):
            try:
                # Initialize model
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                # Generate response
                response = model.generate_content(prompt)
                
                # Handle different response formats
                if hasattr(response, 'text'):
                    return response.text
                elif hasattr(response, 'parts') and response.parts:
                    return response.parts[0].text
                else:
                    raise ValueError("Unexpected response format from Gemini API")
                    
            except Exception as e:
                delay = base_delay * (2 ** attempt)
                print(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                
                if attempt < max_retries - 1:
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print("All retry attempts failed")
                    return "I apologize, but I'm having trouble generating a response right now. Please try again later."
    
    def query_db(self, model, collection, query: str) -> list:
        """Query the vector database for relevant documents.
        
        Args:
            model: The embedding model
            collection: The ChromaDB collection
            query: The user's question
            
        Returns:
            List of relevant documents
        """
        try:
            # Validate inputs
            if not query or not isinstance(query, str):
                raise ValueError("Query must be a non-empty string")
            if not model or not collection:
                raise ValueError("Model and collection must be provided")

            # Get query embedding
            try:
                query_embedding = model.encode([query]).tolist()
            except Exception as e:
                print(f"Error creating embedding: {str(e)}")
                return ["Error: Unable to process your question"]

            # Query the database
            try:
                results = collection.query(
                    query_embeddings=query_embedding,
                    n_results=5,  # Get more results for better context
                    include=['documents', 'metadatas', 'distances']
                )
            except Exception as e:
                print(f"Database query error: {str(e)}")
                return ["Error: Database search failed"]

            # Validate results
            if not results or 'documents' not in results or not results['documents']:
                return ["No relevant information found in the database."]

            # Get documents and their metadata
            try:
                documents = results['documents'][0]
                metadatas = results['metadatas'][0]
                distances = results['distances'][0]
            except (KeyError, IndexError) as e:
                print(f"Error accessing results: {str(e)}")
                return ["Error: Invalid search results format"]

            # Filter and sort results
            filtered_docs = []
            seen_subcategories = set()  # Track unique subcategories
            
            # First pass: Get best match per subcategory
            subcategory_docs = {}
            for doc, meta, dist in zip(documents, metadatas, distances):
                if not isinstance(dist, (int, float)):
                    continue
                    
                subcategory = meta.get('subcategory', 'general')
                if dist < 0.8:  # Basic relevance threshold
                    if subcategory not in subcategory_docs or dist < subcategory_docs[subcategory][1]:
                        subcategory_docs[subcategory] = (doc, dist)
            
            # Sort by distance and take top matches
            sorted_docs = [doc for doc, dist in sorted(subcategory_docs.values(), key=lambda x: x[1])]
            filtered_docs = sorted_docs[:3]  # Take top 3 most relevant docs from different subcategories

            if not filtered_docs:
                return ["I don't have enough relevant information to answer that question accurately."]

            return filtered_docs[:3]  # Return top 3 most relevant docs

        except Exception as e:
            print(f"Unexpected error in query_db: {str(e)}")
            return ["Sorry, I encountered an error while searching the database."]
    
    
    def get_data_from_llm(self, model, collection, query: str) -> str:
        """Get an answer using either API data or LLM based on the query type.
        
        Args:
            model: The embedding model
            collection: The ChromaDB collection
            query: The user's question
            
        Returns:
            The response (either from API or LLM)
        """
        try:
            # Validate inputs
            if not query or not isinstance(query, str):
                return "Error: Invalid query"
            if not model or not collection:
                return "Error: Required components not initialized"

            # Use LLM to classify query
            print("\nClassifying query...")
            data_source, params = self.query_classifier.classify_query(query)
            print(f"Query classified as: {data_source}")
            print(f"Parameters: {params}")
            
            # Handle API queries
            if data_source == 'WALLET_API':
                print("\nFetching wallet data...")
                # try:
                # Get transaction type from params or default to 'all'
                txn_type = params.get('type', 'all')
                print(f"Transaction type: {txn_type}")
                result = self.api_client.analyze_transactions(txn_type)
                print(f"Result: {result}")
                # Format the response based on transaction type
                if isinstance(result, dict):
                    if 'error' in result:
                        return f"Error fetching wallet data: {result['error']}"
                        
                    if txn_type == 'deposit':
                        return f"Total deposits: ₹{result['total_deposit']:,.2f} ({result['deposit_count']} transactions)"
                    elif txn_type == 'withdrawal':
                        return f"Total withdrawals: ₹{result['total_withdrawal']:,.2f} ({result['withdrawal_count']} transactions)"
                    else:
                        return (f"Wallet Summary:\n"
                                f"• Total Deposits: ₹{result['total_deposit']:,.2f} ({result['deposit_count']} transactions)\n"
                                f"• Total Withdrawals: ₹{result['total_withdrawal']:,.2f} ({result['withdrawal_count']} transactions)\n"
                                f"• Net Balance: ₹{result['net_balance']:,.2f}")
                return str(result)
                    
                # except Exception as e:
                #     print(e)
                #     return "Error: Could not process wallet information"

            elif data_source == 'TRADING_API':
                print("\nFetching trading data...")
                result = self.api_client.analyze_trading_history(symbol=params.get('symbol'))
                
                # Format the trading response
                if isinstance(result, dict):
                    if params.get('symbol'):  # Specific symbol analysis
                        symbol = params['symbol']
                        if symbol in result:
                            data = result[symbol]
                            return (f"Trading Summary for {symbol}:\n"
                                   f"• Total Bought: {data['total_buy_quantity']:,.8f} at avg ₹{data['avg_buy_price']:,.2f}\n"
                                   f"• Total Sold: {data['total_sell_quantity']:,.8f} at avg ₹{data['avg_sell_price']:,.2f}\n"
                                   f"• Net Position: {data['net_quantity']:,.8f}\n"
                                   f"• Total Orders: {data['total_orders']}")
                        return f"No trading history found for {symbol}"
                    else:  # Overall trading summary
                        summary = []
                        for symbol, data in result.items():
                            if data['total_orders'] > 0:
                                summary.append(
                                    f"{symbol}:\n"
                                    f"• Net Position: {data['net_quantity']:,.8f}\n"
                                    f"• Average Buy: ₹{data['avg_buy_price']:,.2f}\n"
                                    f"• Average Sell: ₹{data['avg_sell_price']:,.2f}"
                                )
                        return "Trading Summary:\n\n" + "\n\n".join(summary) if summary else "No trading history found."
                return str(result)

            # If no API response, use FAQ database
            print("\nQuerying FAQ database...")
            contexts = self.query_db(model, collection, query)
            if not contexts or (isinstance(contexts, list) and all(c.startswith("Error:") for c in contexts)):
                return "I apologize, but I couldn't find relevant information to answer your question."
            print("*****************")
            print("Context from DB:", contexts)
            print("*****************")
            
            # Build prompt
            print("\nBuilding prompt...")
            try:
                prompt = self.build_prompt(query, contexts, user_trades=None)
            except Exception as e:
                print(f"Error building prompt: {str(e)}")
                return "Error: Failed to process the question"
            print("*****************")
            print("Prompt to LLM:", prompt)
            print("*****************")
            
            # Get answer from Gemini
            print("\nCalling Gemini API...")
            answer = self.call_gemini(prompt)
            if answer.startswith("Error:") or answer.startswith("I apologize"):
                print(f"LLM error response: {answer}")
                return "I apologize, but I'm having trouble generating a response right now."
            print("*****************")
            print("Raw answer:", answer)
            print("*****************")
            
            return answer.strip()
            
        except Exception as e:
            print(f"Critical error in get_data_from_llm: {str(e)}")
            return "I apologize, but I encountered an unexpected error processing your request."