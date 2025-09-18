import uuid
import time
import requests
from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal

# Transaction types
TRANSACTION_TYPE_ALL = 'all'
TRANSACTION_TYPE_DEPOSIT = 'deposit'
TRANSACTION_TYPE_WITHDRAWAL = 'withdrawal'

class CSProAPIClient:
    def __init__(self, auth_token: str, base_url: str = "https://coinswitch.co"):
        self.base_url = base_url
        self.auth_token = auth_token
        self.headers = {
            "Accept": "application/json",
            "x-request-id": str(uuid.uuid4())  # Generate unique request ID for each instance
        }
        self.cookies = {
            "st": auth_token  # Set authentication cookie
        }

    def get_wallet_transactions(self, 
                              limit: int = 100, 
                              deposit_cursor: Optional[float] = None,
                              withdrawal_cursor: Optional[float] = None) -> Dict:
        """Get wallet transactions history.
        
        Args:
            limit: Number of transactions to fetch (default 20)
            deposit_cursor: Timestamp cursor for deposits (e.g., 1758215783.627)
            withdrawal_cursor: Timestamp cursor for withdrawals
        
        Returns:
            Dict containing transaction data
        """
        try:
            url = f"{self.base_url}/pro/api/v1/cspro/wallet-transactions_v2"
            
            # Build query parameters
            params = {"limit": limit}
            
            # Add cursors if provided, otherwise use current timestamp
            current_timestamp = time.time()
            params["deposit_cursor"] = deposit_cursor if deposit_cursor else current_timestamp
            params["withdrawal_cursor"] = withdrawal_cursor if withdrawal_cursor else current_timestamp

            # Make request with authentication cookie
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                cookies=self.cookies
            )
            response.raise_for_status()
            
            # Parse and validate response
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Invalid response format")
                
            return data

        except requests.exceptions.RequestException as e:
            print(f"Error fetching wallet transactions: {str(e)}")
            return {"error": str(e)}
        except ValueError as e:
            print(f"Error parsing response: {str(e)}")
            return {"error": "Invalid response format"}
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return {"error": "Unexpected error occurred"}

    def get_closed_orders(self, page: int = 1) -> Dict:
        """Get closed orders history.
        
        Args:
            page: Page number for pagination (default 1)
        
        Returns:
            Dict containing order data
        """
        try:
            url = f"{self.base_url}/pro/api/v1/cspro/closed-orders"
            
            # Build query parameters
            params = {"page": page}
            
            # Generate new request ID for each call
            self.headers["x-request-id"] = str(uuid.uuid4())
            
            # Make request with authentication cookie
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                cookies=self.cookies
            )
            response.raise_for_status()
            
            # Parse and validate response
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Invalid response format")
                
            return data

        except requests.exceptions.RequestException as e:
            print(f"Error fetching closed orders: {str(e)}")
            return {"error": str(e)}
        except ValueError as e:
            print(f"Error parsing response: {str(e)}")
            return {"error": "Invalid response format"}
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return {"error": "Unexpected error occurred"}

    def analyze_transactions(self, txn_type: str = 'all') -> Dict:
        """Analyze wallet transactions.
        
        Args:
            txn_type: Type of transactions to analyze ('deposit'/'withdrawal'/'all')
        
        Returns:
            Dict containing analysis results
        """
        transactions = self.get_wallet_transactions()
        if "error" in transactions:
            return transactions

        total_deposit = Decimal('0')
        total_withdrawal = Decimal('0')
        deposit_count = 0
        withdrawal_count = 0

        # Process transactions
        for txn in transactions.get('data', {}).get('transactions', []):
            amount = Decimal(str(txn.get('amount', 0)))
            if txn['type'] == 'deposit':
                total_deposit += amount
                deposit_count += 1
            elif txn['type'] == 'withdrawal':
                total_withdrawal += amount
                withdrawal_count += 1

        return {
            "total_deposit": float(total_deposit),
            "total_withdrawal": float(total_withdrawal),
            "net_balance": float(total_deposit - total_withdrawal),
            "deposit_count": deposit_count,
            "withdrawal_count": withdrawal_count,
            "total_transactions": deposit_count + withdrawal_count
        }

    def analyze_trading_history(self, symbol: Optional[str] = None) -> Dict:
        """Analyze trading history for a specific symbol or all symbols.
        
        Args:
            symbol: Specific trading pair to analyze (e.g., 'BTC-INR')
        
        Returns:
            Dict containing trading analysis
        """
        orders = self.get_closed_orders()
        if "error" in orders:
            return orders

        analysis = {}
        for order in orders.get('data', []):
            sym = order.get('symbol')
            if symbol and sym != symbol:
                continue

            if sym not in analysis:
                analysis[sym] = {
                    "total_buy_quantity": Decimal('0'),
                    "total_sell_quantity": Decimal('0'),
                    "total_buy_value": Decimal('0'),
                    "total_sell_value": Decimal('0'),
                    "buy_orders": 0,
                    "sell_orders": 0
                }

            quantity = Decimal(str(order.get('quantity', 0)))
            value = Decimal(str(order.get('value', 0)))
            
            if order['side'] == 'buy':
                analysis[sym]["total_buy_quantity"] += quantity
                analysis[sym]["total_buy_value"] += value
                analysis[sym]["buy_orders"] += 1
            else:
                analysis[sym]["total_sell_quantity"] += quantity
                analysis[sym]["total_sell_value"] += value
                analysis[sym]["sell_orders"] += 1

        # Calculate averages and convert to float for JSON serialization
        for sym in analysis:
            data = analysis[sym]
            buy_qty = data["total_buy_quantity"]
            sell_qty = data["total_sell_quantity"]
            
            analysis[sym].update({
                "avg_buy_price": float(data["total_buy_value"] / buy_qty) if buy_qty > 0 else 0,
                "avg_sell_price": float(data["total_sell_value"] / sell_qty) if sell_qty > 0 else 0,
                "net_quantity": float(buy_qty - sell_qty),
                "total_orders": data["buy_orders"] + data["sell_orders"]
            })

            # Convert Decimal to float for JSON serialization
            for key in ["total_buy_quantity", "total_sell_quantity", "total_buy_value", "total_sell_value"]:
                analysis[sym][key] = float(analysis[sym][key])

        return analysis
