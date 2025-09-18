import chromadb
import os
import ssl
import time
import argparse
import shutil
from sentence_transformers import SentenceTransformer

from helper import BotFacade
from raw_data.docs import (
    FINAL_DOCS as docs,
    INITIAL_DOCS,
    FAQ_DOCS
)

def parse_args():
    parser = argparse.ArgumentParser(description='Vector Database FAQ System')
    parser.add_argument('--reinit-db', action='store_true', 
                      help='Reinitialize the database (warning: deletes existing data)')
    parser.add_argument('--auth-token', type=str, required=True,
                      help='Authentication token for CoinSwitch API')
    parser.add_argument('--test-type', type=str, choices=['wallet', 'trading', 'all'],
                      default='all', help='Type of tests to run (wallet/trading/all)')
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
    # "Show me my last 5 deposits",
    # "How much money have I withdrawn in total?",
    # "What's my current wallet balance?",
    # "Show me my transaction history",
    # "What's my largest deposit amount?",
    # "Show me withdrawals from last month",
    # "What's my average deposit size?",
    # "How many successful deposits have I made?",
    # "Show me my pending transactions"
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

def run_test_queries(queries, test_name, delay=3):
    """Run a set of test queries with proper formatting and delays."""
    success_count = 0
    error_count = 0
    api_errors = 0
    db_errors = 0
    
    print(f"\n{test_name}")
    print("=" * len(test_name))
    
    for i, query in enumerate(queries, 1):
        print(f"\nTest {i}/{len(queries)}")
        print(f"Query: {query}")
        print("-" * 50)
        
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
            else:
                error_count += 1
                if "API" in answer:
                    api_errors += 1
                else:
                    db_errors += 1
                print(f"\nError in response: {answer}")
                
        except Exception as e:
            error_count += 1
            print(f"\nError processing query: {str(e)}")
            if "API" in str(e):
                api_errors += 1
            else:
                db_errors += 1
        
        print("\n" + "=" * 80)
        
        # Add delay between queries
        if i < len(queries):
            print(f"\nWaiting {delay} seconds before next query...")
            try:
                time.sleep(delay)
            except KeyboardInterrupt:
                print("\nTesting interrupted by user")
                break
    
    # Print summary
    print(f"\nTest Summary for {test_name}")
    print("-" * (len(test_name) + 16))
    print(f"Total Queries: {len(queries)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {error_count}")
    if error_count > 0:
        print(f"  API Errors: {api_errors}")
        print(f"  DB Errors: {db_errors}")
    print(f"Success Rate: {(success_count/len(queries))*100:.1f}%")
    
    return success_count, error_count

# Validate environment before starting tests
if not validate_environment():
    raise SystemExit("Environment validation failed")

print("\nStarting tests...")
total_success = 0
total_errors = 0

try:
    # Run tests based on selected type
    if args.test_type in ['wallet', 'all']:
        success, errors = run_test_queries(
            wallet_test_queries,
            "Testing Wallet API Queries",
            delay=args.delay
        )
        total_success += success
        total_errors += errors

    if args.test_type in ['trading', 'all']:
        success, errors = run_test_queries(
            trading_test_queries,
            "Testing Trading API Queries",
            delay=args.delay
        )
        total_success += success
        total_errors += errors

    if args.test_type == 'all':
        print("\nStarting combined API and FAQ tests...")
        success, errors = run_test_queries(
            test_queries,
            "Testing Combined Queries",
            delay=args.delay
        )
        total_success += success
        total_errors += errors

    # Print overall summary
    total_queries = len(wallet_test_queries) + len(trading_test_queries) + len(test_queries)
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

