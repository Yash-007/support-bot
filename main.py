import chromadb
import os
import ssl
import time
import json
import argparse
import shutil
from datetime import datetime
from sentence_transformers import SentenceTransformer
from flask import Flask, request, jsonify

from helper import BotFacade
from raw_data.docs import (
    FINAL_DOCS as docs,
    INITIAL_DOCS,
    FAQ_DOCS
)

from portfolio import PortfolioAnalyzer

def parse_args():
    parser = argparse.ArgumentParser(description='Vector Database FAQ System')
    parser.add_argument('--reinit-db', action='store_true', 
                      help='Reinitialize the database (warning: deletes existing data)')
    # parser.add_argument('--auth-token', type=str, required=True,
    #                   help='Authentication token for CoinSwitch API')
    parser.add_argument('--test-type', type=str, choices=['wallet', 'trading', 'fees', 'all'],
                      default='all', help='Type of tests to run (wallet/trading/fees/all)')
    parser.add_argument('--delay', type=int, default=3,
                      help='Delay between queries in seconds (default: 3)')
    return parser.parse_args()

def validate_environment():
    """Validate all required components are properly initialized."""
    try:
        # Check SSL environment
        if not hasattr(ssl, '_create_unverified_context'):
            raise EnvironmentError("SSL context creation not available")
            
        # Check required environment variables
        if not os.environ.get('CURL_CA_BUNDLE') == '':
            print("Warning: CURL_CA_BUNDLE not set to empty string")
            
        return True
    except Exception as e:
        print(f"Environment validation failed: {str(e)}")
        return False

# Parse command line arguments
args = parse_args()

# Disable SSL verification globally
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['CURL_CA_BUNDLE'] = ''


# Initialize components with error handling
try:
    print("\nInitializing database...")
    db_path = "./chroma_db"
    
    # If reinit flag is set, delete existing database
    if args.reinit_db:
        if os.path.exists(db_path):
            print("Reinitializing database: Removing existing data...")
            shutil.rmtree(db_path)
            print("Existing database removed.")
        should_add_docs = True
    
    # Initialize client
    client = chromadb.PersistentClient(path=db_path)
    
    # Check if collection exists and get its size
    try:
        collection = client.get_collection(name="faq")
        existing_count = collection.count()
        print(f"Found existing collection with {existing_count} documents")
        
        if existing_count > 0 and not args.reinit_db:
            print("Using existing database. Use --reinit-db flag to reinitialize.")
            should_add_docs = False
        else:
            if args.reinit_db:
                print("Reinitializing collection...")
                client.delete_collection(name="faq")
            print("Creating new collection...")
            collection = client.create_collection(
                name="faq",
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity for better matching
            )
            should_add_docs = True
            
    except Exception as e:
        print("Creating new collection...")
        collection = client.create_collection(
            name="faq",
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity for better matching
        )
        should_add_docs = True
    
    print("Database initialized successfully!")
except Exception as e:
    print(f"Error initializing database: {str(e)}")
    raise SystemExit("Cannot continue without database")

try:
    print("\nLoading embedding model...")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    print("Model loaded successfully!")
except Exception as e:
    print(f"Error loading model: {str(e)}")
    raise SystemExit("Cannot continue without embedding model")

###### CREATE EMBEDDINGS IF NEEDED #########
if should_add_docs:
    try:
        print("\nEncoding documents...")
        if not docs:
            raise ValueError("No documents to encode")
        embeddings = model.encode(docs).tolist()
        ids = [f"doc{i+1}" for i in range(len(docs))]
        print(f"Successfully encoded {len(docs)} documents!")
    except Exception as e:
        print(f"Error encoding documents: {str(e)}")
        raise SystemExit("Cannot continue without document embeddings")

# Only process metadata and update database if needed
if should_add_docs:
    print("Creating metadata...")
    metadatas = []
    for doc in docs:
        # Default metadata with all required fields as simple types
        metadata = {
            "type": "general",
            "category": "general",
            "subcategory": "general",
            "keywords": ""
        }
        
        # Try to extract metadata from FAQ format
        try:
            if isinstance(doc, str) and 'Category:' in doc and 'Type:' in doc:
                lines = doc.split('\n')
                for line in lines:
                    if line.startswith('Category:'):
                        metadata['category'] = line.split(': ')[1].strip()
                    elif line.startswith('Subcategory:'):
                        metadata['subcategory'] = line.split(': ')[1].strip()
                    elif line.startswith('Type:'):
                        metadata['type'] = line.split(': ')[1].strip()
                    elif line.startswith('Keywords:'):
                        # Store keywords as comma-separated string instead of list
                        metadata['keywords'] = line.split(': ')[1].strip()
            elif 'KYC' in doc:
                metadata = {
                    "type": "kyc",
                    "category": "kyc",
                    "subcategory": "verification"
                }
            elif 'Smart Invest' in doc:
                metadata = {
                    "type": "trading",
                    "category": "smart_invest",
                    "subcategory": "automated_trading"
                }
        except Exception as e:
            print(f"Warning: Error processing metadata for doc: {str(e)}")
            # Keep default metadata
            
        metadatas.append(metadata)

    # Validate data consistency
    try:
        if not (len(docs) == len(embeddings) == len(ids) == len(metadatas)):
            raise ValueError(
                f"Inconsistent lengths: docs={len(docs)}, embeddings={len(embeddings)}, "
                f"ids={len(ids)}, metadatas={len(metadatas)}"
            )

        # Print some stats
        print("\nDatabase Statistics:")
        print(f"Total documents: {len(docs)}")
        print(f"Initial docs: {len(INITIAL_DOCS)}")
        print(f"FAQ docs: {len(FAQ_DOCS)}")
        print(f"Metadata entries: {len(metadatas)}")

        # Add to database
        print("\nAdding documents to the database...")
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=docs,
            metadatas=metadatas
        )
        print("Database updated successfully!")

        # Verify database content
        collection_count = collection.count()
        if collection_count != len(docs):
            print(f"Warning: Database count ({collection_count}) doesn't match document count ({len(docs)})")
        else:
            print(f"Database verification successful: {collection_count} documents stored")

    except Exception as e:
        print(f"Error updating database: {str(e)}")
        raise SystemExit("Cannot continue without database update")
else:
    print("\nUsing existing database:")
    print(f"Total documents in database: {collection.count()}")

############## Test Queries ##############
bot = BotFacade(auth_token=args.auth_token)

# Wallet API specific test queries
wallet_test_queries = [
    "What's my total deposit amount in my wallet?",
    "Show me my last 5 deposits",
    "How much money have I withdrawn in total?",
    "What's my current wallet balance?",
    "Show me my transaction history",
    "What's my largest deposit amount?",
    "Show me withdrawals from last month",
    "What's my average deposit size?",
    "How many successful deposits have I made?",
    "Show me my pending transactions"
]

# Trading API specific test queries
trading_test_queries = [
    "What's my average purchase price for BTC?",
    "Show me all my closed orders for ETH",
    "How much Bitcoin have I bought in total?",
    "What's my total trading volume?",
    "Show me my ETH trading history",
    "What's my profit/loss on BTC trades?",
    "Show me my largest trade",
    "What's my average selling price for ETH?",
    "How many trades did I make last month?",
    "Show me my open orders"
]

# Fees specific test queries
fees_test_queries = [
    "What are the spot trading fees?",
    "Show me futures trading fees for INR pairs",
    "What are the maker fees for USDT futures?",
    "Tell me about options trading fees",
    "What are the taker fees for spot trading?",
    "Show me all trading fees",
    "What's the fee structure for high volume traders?",
    "Tell me about VIP level fees in futures",
    "What are the fees for options trading in USDT?",
    "How do maker and taker fees work?"
]

# Combined test queries for general testing
test_queries = [
    # Mixed Queries (API + FAQ combination)
    "What are the trading fees and how much have I paid in fees so far?",
    "Explain the withdrawal process and show my withdrawal history",
    "What's my wallet balance and what are the withdrawal limits?",
    "Show me my BTC trades and explain the trading fees",
    
    # FAQ/Documentation Queries
    "What documents do I need for KYC verification?",
    "How does futures trading work on your platform?",
    "What happens if my deposit fails?",
    "How secure is my crypto on this platform?",
    "What are the different types of orders I can place?",
    "How do I change my bank details?"
]

def save_trading_results(test_results: dict):
    """Save trading results to a separate file, overwriting previous results."""
    try:
        results_file = "trading_results.json"
        trading_results = {
            "last_run": datetime.now().isoformat(),
            "queries": []
        }
        
        # Extract trading-specific results from test_results
        for query in test_results.get("queries", []):
            trading_results["queries"].append({
                "query": query.get("query", ""),
                "timestamp": query.get("timestamp", ""),
                "processing_time": query.get("processing_time", 0),
                "answer": query.get("answer", ""),
                "status": query.get("status", "unknown")
            })
        
        with open(results_file, 'w') as f:
            json.dump(trading_results, f, indent=2)
        print(f"\nTrading results saved to {results_file}")
    except Exception as e:
        print(f"\nWarning: Could not save trading results to file: {str(e)}")

def run_test_queries(queries, test_name, delay=3):
    """Run a set of test queries with proper formatting and delays."""
    success_count = 0
    error_count = 0
    api_errors = 0
    db_errors = 0
    
    # Initialize test results
    test_results = {
        "test_name": test_name,
        "timestamp": datetime.now().isoformat(),
        "total_queries": len(queries),
        "queries": []
    }
    
    print(f"\n{test_name}")
    print("=" * len(test_name))
    
    for i, query in enumerate(queries, 1):
        print(f"\nTest {i}/{len(queries)}")
        print(f"Query: {query}")
        print("-" * 50)
        
        query_result = {
            "query": query,
            "query_number": i,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Validate query
            if not query or not isinstance(query, str):
                raise ValueError("Invalid query format")
                
            # Process query
            start_time = time.time()
            answer = bot.get_data_from_llm(model, collection, query)
            processing_time = time.time() - start_time
            
            # Check response
            if answer and not answer.startswith("Error:"):
                success_count += 1
                print(f"\nAnswer: {answer}")
                print(f"Processing time: {processing_time:.2f} seconds")
                query_result.update({
                    "status": "success",
                    "answer": answer,
                    "processing_time": round(processing_time, 2)
                })
            else:
                error_count += 1
                if "API" in answer:
                    api_errors += 1
                    error_type = "api_error"
                else:
                    db_errors += 1
                    error_type = "db_error"
                print(f"\nError in response: {answer}")
                query_result.update({
                    "status": "error",
                    "error_type": error_type,
                    "error_message": answer,
                    "processing_time": round(processing_time, 2)
                })
                
        except Exception as e:
            error_count += 1
            error_msg = str(e)
            print(f"\nError processing query: {error_msg}")
            if "API" in error_msg:
                api_errors += 1
                error_type = "api_error"
            else:
                db_errors += 1
                error_type = "db_error"
            query_result.update({
                "status": "error",
                "error_type": error_type,
                "error_message": error_msg
            })
        
        # Add query result to test results
        test_results["queries"].append(query_result)
        
        print("\n" + "=" * 80)
        
        # Add delay between queries
        if i < len(queries):
            print(f"\nWaiting {delay} seconds before next query...")
            try:
                time.sleep(delay)
            except KeyboardInterrupt:
                print("\nTesting interrupted by user")
                test_results["status"] = "interrupted"
                break
    
    # Add summary to test results
    test_results.update({
        "summary": {
            "success_count": success_count,
            "error_count": error_count,
            "api_errors": api_errors,
            "db_errors": db_errors,
            "success_rate": round((success_count/len(queries))*100, 1)
        },
        "status": test_results.get("status", "completed")
    })
    
    # Print summary
    print(f"\nTest Summary for {test_name}")
    print("-" * (len(test_name) + 16))
    print(f"Total Queries: {len(queries)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {error_count}")
    if error_count > 0:
        print(f"  API Errors: {api_errors}")
        print(f"  DB Errors: {db_errors}")
    print(f"Success Rate: {test_results['summary']['success_rate']}%")
    
    # Save results to file
    try:
        results_file = "test_results.json"
        if os.path.exists(results_file):
            with open(results_file, 'r') as f:
                all_results = json.load(f)
        else:
            all_results = {"test_runs": []}
            
        all_results["test_runs"].append(test_results)
        
        with open(results_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"\nTest results saved to {results_file}")
        
    except Exception as e:
        print(f"\nWarning: Could not save test results to file: {str(e)}")
    
    return success_count, error_count, test_results

# Validate environment before starting tests
if not validate_environment():
    raise SystemExit("Environment validation failed")

print("\nStarting tests...")
total_success = 0
total_errors = 0

try:
    # Run tests based on selected type
    if args.test_type in ['wallet', 'all']:
        success, errors, _ = run_test_queries(
            wallet_test_queries,
            "Testing Wallet API Queries",
            delay=args.delay
        )
        total_success += success
        total_errors += errors

    if args.test_type in ['trading', 'all']:
        success, errors, test_results = run_test_queries(
            trading_test_queries,
            "Testing Trading API Queries",
            delay=args.delay
        )
        
        # Save trading specific results
        save_trading_results(test_results)
        
        total_success += success
        total_errors += errors

    if args.test_type in ['fees', 'all']:
        success, errors, _ = run_test_queries(
            fees_test_queries,
            "Testing Fees Queries",
            delay=args.delay
        )
        total_success += success
        total_errors += errors

    if args.test_type == 'all':
        print("\nStarting combined API and FAQ tests...")
        success, errors, _ = run_test_queries(
            test_queries,
            "Testing Combined Queries",
            delay=args.delay
        )
        total_success += success
        total_errors += errors

    # Print overall summary
    total_queries = len(wallet_test_queries) + len(trading_test_queries) + len(fees_test_queries) + len(test_queries)
    print("\nOverall Test Summary")
    print("===================")
    print(f"Total Queries Run: {total_success + total_errors}")
    print(f"Total Successful: {total_success}")
    print(f"Total Failed: {total_errors}")
    if total_queries > 0:
        print(f"Overall Success Rate: {(total_success/(total_success + total_errors))*100:.1f}%")

except KeyboardInterrupt:
    print("\nTesting interrupted by user")
except Exception as e:
    print(f"\nUnexpected error during testing: {str(e)}")
finally:
    print("\nTesting completed")
    time.sleep(2)  # Small delay between queries

if __name__ == "__main__":
    app = Flask(__name__)
    
    @app.route("/portfolio-chart", methods=["GET"])
    def portfolio_chart():
        auth_token = request.cookies.get("st")
        if not auth_token:
            return jsonify({"error": "Missing authentication token (cookie 'st' not found)"}), 401

        try:
            symbol = request.args["symbol"]
            from_time = int(request.args["from_time"])
            to_time = int(request.args["to_time"])
            c_duration = int(request.args["c_duration"])
            exchange = request.args["exchange"]

            analyzer = PortfolioAnalyzer(auth_token=auth_token, verify_ssl=False)
            chart_data = analyzer.generate_portfolio_series(
                symbol=symbol,
                from_time=from_time,
                to_time=to_time,
                c_duration=c_duration,
                exchange=exchange
            )
            return jsonify({"data": chart_data, "status": "success"}), 200
        except Exception as e:
            return jsonify({"error": str(e), "status": "error"}), 500
    
    @app.route("/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok"}), 200

    @app.route("/chat", methods=["POST"])
    def query():
        
        # Get 'st' cookie from request and use as auth token
        auth_token = request.cookies.get("st")
        if not auth_token:
            return jsonify({"error": "Missing authentication token (cookie 'st' not found)"}), 401
        bot = BotFacade(auth_token=auth_token)

        data = request.get_json()
        user_query = data.get("query", "")
        if not user_query:
            return jsonify({"error": "No query provided"}), 400
        try:
            answer = bot.get_data_from_llm(model, collection, user_query)
            return jsonify({"answer": answer, "status": "success"}), 200
        except Exception as e:
            return jsonify({"error": str(e), "status": "error"}), 500

    app.run(host="0.0.0.0", port=5000)
