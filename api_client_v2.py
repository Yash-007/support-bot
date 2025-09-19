import uuid
import time
import json
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import os

class CSProAPIClient:
    def __init__(self, auth_token: str, base_url: str = "https://coinswitch.co"):
        self.base_url = base_url
        self.auth_token = auth_token
        self.headers = {
            "Accept": "application/json",
            "x-request-id": str(uuid.uuid4())
        }
        self.cookies = {
            "st": auth_token
        }
        
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)

    def log_api_response(self, endpoint: str, response_data: dict):
        """Log raw API response data to a file."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"logs/api_response_{timestamp}.json"
            
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "endpoint": endpoint,
                "response_data": response_data
            }
            
            with open(filename, 'w') as f:
                json.dump(log_data, f, indent=2)
                
            print(f"\nAPI response logged to: {filename}")
            
        except Exception as e:
            print(f"Warning: Failed to log API response: {str(e)}")

    def get_wallet_transactions(self, limit: int = 100, deposit_cursor: str = "", withdrawal_cursor: str = "") -> Dict:
        """Get wallet transaction history."""
        try:
            url = f"{self.base_url}/pro/api/v1/cspro/wallet-transactions_v2"
            params = {
                "limit": limit,
                "deposit_cursor": deposit_cursor,
                "withdrawal_cursor": withdrawal_cursor
            }
            self.headers["x-request-id"] = str(uuid.uuid4())
            
            print("\n" + "="*50)
            print("API Request: GET /pro/api/v1/cspro/wallet-transactions_v2")
            print(f"Parameters: {json.dumps(params, indent=2)}")
            print("="*50)
            
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                cookies=self.cookies
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Log raw API response
            self.log_api_response("/pro/api/v1/cspro/wallet-transactions_v2", data)
            
            if not isinstance(data, dict):
                raise ValueError("Invalid response format")
                
            return data

        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching wallet transactions: {str(e)}"
            print(f"\nAPI Error: {error_msg}")
            print("="*50)
            return {"error": error_msg}
        except ValueError as e:
            error_msg = f"Error parsing response: {str(e)}"
            print(f"\nParsing Error: {error_msg}")
            print("="*50)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"\nUnexpected Error: {error_msg}")
            print("="*50)
            return {"error": error_msg}

    def analyze_transactions(self, txn_type: Optional[str] = None) -> Dict:
        """Analyze wallet transactions."""
        print(f"\nAnalyzing wallet transactions for type: {txn_type or 'all'}")
        
        transactions = self.get_wallet_transactions()
        if "error" in transactions:
            return transactions

        analysis = {
            "deposits": {
                "total_amount": float(0),  # Initialize as float instead of Decimal
                "count": 0,
                "latest": [],
                "sources": set(),
                "currencies": set()
            },
            "withdrawals": {
                "total_amount": float(0),  # Initialize as float instead of Decimal
                "count": 0,
                "latest": [],
                "destinations": set(),
                "currencies": set()
            }
        }

        print("\nProcessing transactions...")
        
        # Process deposits
        for deposit in transactions.get('data', {}).get('deposits', []):
            try:
                if txn_type and txn_type.lower() != 'deposit':
                    continue
                    
                amount = float(deposit.get('amount', 0))  # Convert to float immediately
                currency = deposit.get('currency', '').upper()
                source = deposit.get('source', '')
                status = deposit.get('status', '').upper()
                
                if status == 'COMPLETED':
                    analysis['deposits']['total_amount'] += amount
                    analysis['deposits']['count'] += 1
                    analysis['deposits']['sources'].add(source)
                    analysis['deposits']['currencies'].add(currency)
                    
                    # Track latest deposits (keep last 5)
                    deposit_info = {
                        'amount': amount,
                        'currency': currency,
                        'source': source,
                        'timestamp': deposit.get('created_at', '')
                    }
                    analysis['deposits']['latest'].append(deposit_info)
                    analysis['deposits']['latest'] = sorted(
                        analysis['deposits']['latest'],
                        key=lambda x: x['timestamp'],
                        reverse=True
                    )[:5]
                    
            except (TypeError, ValueError, KeyError) as e:
                print(f"Error processing deposit: {str(e)}")
                continue

        # Process withdrawals
        for withdrawal in transactions.get('data', {}).get('withdrawals', []):
            try:
                if txn_type and txn_type.lower() != 'withdrawal':
                    continue
                    
                amount = float(withdrawal.get('amount', 0))  # Convert to float immediately
                currency = withdrawal.get('currency', '').upper()
                destination = withdrawal.get('destination', '')
                status = withdrawal.get('status', '').upper()
                
                if status == 'COMPLETED':
                    analysis['withdrawals']['total_amount'] += amount
                    analysis['withdrawals']['count'] += 1
                    analysis['withdrawals']['destinations'].add(destination)
                    analysis['withdrawals']['currencies'].add(currency)
                    
                    # Track latest withdrawals (keep last 5)
                    withdrawal_info = {
                        'amount': amount,
                        'currency': currency,
                        'destination': destination,
                        'timestamp': withdrawal.get('created_at', '')
                    }
                    analysis['withdrawals']['latest'].append(withdrawal_info)
                    analysis['withdrawals']['latest'] = sorted(
                        analysis['withdrawals']['latest'],
                        key=lambda x: x['timestamp'],
                        reverse=True
                    )[:5]
                    
            except (TypeError, ValueError, KeyError) as e:
                print(f"Error processing withdrawal: {str(e)}")
                continue

        # Convert sets to lists for JSON serialization
        analysis['deposits']['sources'] = list(analysis['deposits']['sources'])
        analysis['deposits']['currencies'] = list(analysis['deposits']['currencies'])
        analysis['withdrawals']['destinations'] = list(analysis['withdrawals']['destinations'])
        analysis['withdrawals']['currencies'] = list(analysis['withdrawals']['currencies'])

        print("\nAnalysis Summary:")
        print("="*50)
        print("\nDeposits:")
        print(f"• Total Amount: ₹{analysis['deposits']['total_amount']:,.2f}")
        print(f"• Count: {analysis['deposits']['count']}")
        print(f"• Currencies: {', '.join(analysis['deposits']['currencies'])}")
        print(f"• Sources: {', '.join(analysis['deposits']['sources'])}")
        if analysis['deposits']['latest']:
            print("\nLatest Deposits:")
            for deposit in analysis['deposits']['latest']:
                print(f"• {deposit['currency']} {deposit['amount']:,.2f} from {deposit['source']}")
                print(f"  {deposit['timestamp']}")
        
        print("\nWithdrawals:")
        print(f"• Total Amount: ₹{analysis['withdrawals']['total_amount']:,.2f}")
        print(f"• Count: {analysis['withdrawals']['count']}")
        print(f"• Currencies: {', '.join(analysis['withdrawals']['currencies'])}")
        print(f"• Destinations: {', '.join(analysis['withdrawals']['destinations'])}")
        if analysis['withdrawals']['latest']:
            print("\nLatest Withdrawals:")
            for withdrawal in analysis['withdrawals']['latest']:
                print(f"• {withdrawal['currency']} {withdrawal['amount']:,.2f} to {withdrawal['destination']}")
                print(f"  {withdrawal['timestamp']}")
        print("="*50)
        
        return analysis

    def get_closed_orders(self, page: int = 1) -> Dict:
        """Get closed orders history."""
        try:
            url = f"{self.base_url}/pro/api/v1/cspro/closed-orders"
            params = {"page": page}
            self.headers["x-request-id"] = str(uuid.uuid4())
            
            print("\n" + "="*50)
            print("API Request: GET /pro/api/v1/cspro/closed-orders")
            print(f"Parameters: {json.dumps(params, indent=2)}")
            print("="*50)
            
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                cookies=self.cookies
            )
            response.raise_for_status()
            
            data = response.json()
            order_count = len(data.get('data', {}).get('orders', []))
            
            # Log raw API response
            self.log_api_response("/pro/api/v1/cspro/closed-orders", data)
            
            print("\nAPI Response Summary:")
            print(f"Status: {response.status_code}")
            print(f"Orders received: {order_count}")
            print("="*50)
            
            if not isinstance(data, dict):
                raise ValueError("Invalid response format")
                
            return data

        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching closed orders: {str(e)}"
            print(f"\nAPI Error: {error_msg}")
            print("="*50)
            return {"error": error_msg}
        except ValueError as e:
            error_msg = f"Error parsing response: {str(e)}"
            print(f"\nParsing Error: {error_msg}")
            print("="*50)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"\nUnexpected Error: {error_msg}")
            print("="*50)
            return {"error": error_msg}

    def analyze_trading_history(self, symbol: Optional[str] = None) -> Dict:
        """Analyze trading history for a specific symbol or all symbols."""
        print(f"\nAnalyzing trading history for symbol: {symbol or 'all'}")
        
        orders = self.get_closed_orders()
        if "error" in orders:
            return orders

        analysis = {}
        print("\nProcessing orders...")
        
        # Process each order
        for order in orders.get('data', {}).get('orders', []):
            try:
                # Get currency info
                base_curr = order.get('destination_currency', '').lower()
                if symbol and base_curr != symbol.lower():
                    continue

                # Initialize symbol data if not exists
                if base_curr not in analysis:
                    analysis[base_curr] = {
                        "executed_orders": 0,
                        "cancelled_orders": 0,
                        "total_volume_inr": float(0),  # Initialize as float
                        "total_leverage": float(0),    # Initialize as float
                        "order_count": 0,
                        "buy_orders": {
                            "count": 0,
                            "volume_inr": float(0),    # Initialize as float
                            "avg_price": float(0),     # Initialize as float
                            "total_qty": float(0)      # Initialize as float
                        },
                        "sell_orders": {
                            "count": 0,
                            "volume_inr": float(0),    # Initialize as float
                            "avg_price": float(0),     # Initialize as float
                            "total_qty": float(0)      # Initialize as float
                        },
                        "last_trade": None
                    }

                # Extract order details
                status = order.get('order_execution_status', '')
                trade_type = order.get('trade_type', '').lower()
                executed_qty = float(order.get('executed_quantity', 0))  # Convert to float
                avg_price = float(order.get('average_execution_price', 0))  # Convert to float
                inr_amount = float(order.get('inr_amount', 0))  # Convert to float
                created_at = order.get('created_at', '')
                
                # Update general stats
                analysis[base_curr]["order_count"] += 1
                
                if status == 'EXECUTED':
                    analysis[base_curr]["executed_orders"] += 1
                    
                    # Update side-specific stats
                    side_data = analysis[base_curr]["buy_orders"] if trade_type == 'buy' else analysis[base_curr]["sell_orders"]
                    side_data["count"] += 1
                    side_data["volume_inr"] += inr_amount
                    side_data["total_qty"] += executed_qty
                    if side_data["count"] > 0:
                        side_data["avg_price"] = avg_price if avg_price > 0 else 0
                    
                elif status == 'DELETED' or status == 'CANCELLED':
                    analysis[base_curr]["cancelled_orders"] += 1

                # Update total volume for executed orders
                if status == 'EXECUTED':
                    analysis[base_curr]["total_volume_inr"] += inr_amount

                # Track last trade
                if status == 'EXECUTED':
                    order_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    if not analysis[base_curr]["last_trade"] or order_time > datetime.fromisoformat(analysis[base_curr]["last_trade"]["created_at"].replace('Z', '+00:00')):
                        analysis[base_curr]["last_trade"] = {
                            "side": trade_type,
                            "price": float(avg_price),  # Convert to float
                            "quantity": float(executed_qty),  # Convert to float
                            "created_at": created_at,
                            "status": status,
                            "inr_amount": float(inr_amount)  # Convert to float
                        }

            except (TypeError, ValueError, KeyError) as e:
                print(f"Error processing order: {str(e)}")
                continue

        print("\nAnalysis Summary:")
        print("="*50)
        for symbol, data in analysis.items():
            print(f"\n{symbol.upper()} Trading Summary:")
            print(f"• Total Orders: {data['order_count']}")
            print(f"  - Executed: {data['executed_orders']}")
            print(f"  - Cancelled: {data['cancelled_orders']}")
            print(f"• Total Volume: ₹{data['total_volume_inr']:,.2f}")
            print("\nBuy Orders:")
            print(f"• Count: {data['buy_orders']['count']}")
            print(f"• Volume: ₹{data['buy_orders']['volume_inr']:,.2f}")
            print(f"• Average Price: ₹{data['buy_orders']['avg_price']:,.2f}")
            print(f"• Total Quantity: {data['buy_orders']['total_qty']:.8f}")
            print("\nSell Orders:")
            print(f"• Count: {data['sell_orders']['count']}")
            print(f"• Volume: ₹{data['sell_orders']['volume_inr']:,.2f}")
            print(f"• Average Price: ₹{data['sell_orders']['avg_price']:,.2f}")
            print(f"• Total Quantity: {data['sell_orders']['total_qty']:.8f}")
            if data['last_trade']:
                print("\nLast Trade:")
                print(f"• {data['last_trade']['side'].upper()} {data['last_trade']['quantity']:.8f}")
                print(f"• Price: ₹{data['last_trade']['price']:,.2f}")
                print(f"• Value: ₹{data['last_trade']['inr_amount']:,.2f}")
                print(f"• Time: {data['last_trade']['created_at']}")
            print("-"*50)
        
        return analysis

    def get_portfolio_data(self) -> Dict:
        """Get portfolio data."""
        try:
            url = f"{self.base_url}/pro/api/v1/cspro/portfolio_data"
            self.headers["x-request-id"] = str(uuid.uuid4())
            self.headers["content-type"] = "application/json"
            
            print("\n" + "="*50)
            print("API Request: POST /pro/api/v1/cspro/portfolio_data")
            print("="*50)
            
            response = requests.post(
                url,
                headers=self.headers,
                cookies=self.cookies
            )
            response.raise_for_status()
            
            data = response.json()
            print("portfolio data", data)
            
            # Log raw API response
            self.log_api_response("/pro/api/v1/cspro/portfolio_data", data)
            
            if not isinstance(data, dict):
                raise ValueError("Invalid response format")
                
            return data

        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching portfolio data: {str(e)}"
            print(f"\nAPI Error: {error_msg}")
            print("="*50)
            return {"error": error_msg}
        except ValueError as e:
            error_msg = f"Error parsing response: {str(e)}"
            print(f"\nParsing Error: {error_msg}")
            print("="*50)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"\nUnexpected Error: {error_msg}")
            print("="*50)
            return {"error": error_msg}

    def analyze_portfolio(self, currency: Optional[str] = None) -> Dict:
        """Analyze portfolio data for all or specific currency."""
        print(f"\nAnalyzing portfolio data for currency: {currency or 'all'}")
        
        portfolio = self.get_portfolio_data()
        if "error" in portfolio:
            return portfolio

        analysis = {
            "total_invested": float(0),
            "total_current_value": float(0),
            "total_pnl": float(0),
            "assets": {},
            "summary": {
                "total_assets": 0,
                "profitable_assets": 0,
                "loss_making_assets": 0
            }
        }

        print("\nProcessing portfolio...")
        
        # Process each asset
        for asset in portfolio.get('data', []):
            try:
                curr = asset.get('currency', '').lower()
                if currency and curr != currency.lower():
                    continue

                # Get asset details
                main_balance = float(asset.get('main_balance', 0))
                buy_avg_price = float(asset.get('buy_average_price', 0))
                invested_value = float(asset.get('invested_value', 0))
                current_value = float(asset.get('current_value', 0))
                current_price = float(asset.get('sell_rate', 0))
                
                # Calculate PnL
                pnl = current_value - invested_value
                pnl_percentage = (pnl / invested_value * 100) if invested_value > 0 else 0
                
                # Store asset analysis
                analysis['assets'][curr] = {
                    "name": asset.get('name', ''),
                    "balance": main_balance,
                    "buy_average_price": buy_avg_price,
                    "current_price": current_price,
                    "invested_value": invested_value,
                    "current_value": current_value,
                    "pnl": pnl,
                    "pnl_percentage": pnl_percentage,
                    "blocked": {
                        "deposit": float(asset.get('blocked_balance_deposit', 0)),
                        "withdraw": float(asset.get('blocked_balance_withdraw', 0)),
                        "order": float(asset.get('blocked_balance_order', 0)),
                        "stake": float(asset.get('blocked_balance_stake', 0)),
                        "vault": float(asset.get('blocked_balance_vault', 0)),
                        "future": float(asset.get('blocked_balance_future', 0))
                    }
                }
                
                # Update totals
                analysis['total_invested'] += invested_value
                analysis['total_current_value'] += current_value
                analysis['total_pnl'] += pnl
                
                # Update summary
                analysis['summary']['total_assets'] += 1
                if pnl >= 0:
                    analysis['summary']['profitable_assets'] += 1
                else:
                    analysis['summary']['loss_making_assets'] += 1

            except (TypeError, ValueError, KeyError) as e:
                print(f"Error processing asset {curr}: {str(e)}")
                continue

        # Calculate overall PnL percentage
        if analysis['total_invested'] > 0:
            analysis['total_pnl_percentage'] = (analysis['total_pnl'] / analysis['total_invested']) * 100
        else:
            analysis['total_pnl_percentage'] = 0

        print("\nPortfolio Summary:")
        print("="*50)
        print(f"Total Assets: {analysis['summary']['total_assets']}")
        print(f"Total Invested: ₹{analysis['total_invested']:,.2f}")
        print(f"Current Value: ₹{analysis['total_current_value']:,.2f}")
        print(f"Overall P&L: ₹{analysis['total_pnl']:,.2f} ({analysis['total_pnl_percentage']:,.2f}%)")
        print(f"Profitable Assets: {analysis['summary']['profitable_assets']}")
        print(f"Loss Making Assets: {analysis['summary']['loss_making_assets']}")
        
        if currency:
            asset = analysis['assets'].get(currency.lower())
            if asset:
                print(f"\n{asset['name']} ({currency.upper()}) Details:")
                print(f"Balance: {asset['balance']:.8f}")
                print(f"Buy Average: ₹{asset['buy_average_price']:,.2f}")
                print(f"Current Price: ₹{asset['current_price']:,.2f}")
                print(f"Invested Value: ₹{asset['invested_value']:,.2f}")
                print(f"Current Value: ₹{asset['current_value']:,.2f}")
                print(f"P&L: ₹{asset['pnl']:,.2f} ({asset['pnl_percentage']:,.2f}%)")
        
        print("="*50)
        return analysis