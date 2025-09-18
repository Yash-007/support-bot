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
                        "total_volume_inr": Decimal('0'),
                        "total_leverage": Decimal('0'),
                        "order_count": 0,
                        "buy_orders": {
                            "count": 0,
                            "volume_inr": Decimal('0'),
                            "avg_price": Decimal('0'),
                            "total_qty": Decimal('0')
                        },
                        "sell_orders": {
                            "count": 0,
                            "volume_inr": Decimal('0'),
                            "avg_price": Decimal('0'),
                            "total_qty": Decimal('0')
                        },
                        "last_trade": None
                    }

                # Extract order details
                status = order.get('order_execution_status', '')
                trade_type = order.get('trade_type', '').lower()
                executed_qty = Decimal(str(order.get('executed_quantity', 0)))
                avg_price = Decimal(str(order.get('average_execution_price', 0)))
                inr_amount = Decimal(str(order.get('inr_amount', 0)))
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
                            "price": float(avg_price),
                            "quantity": float(executed_qty),
                            "created_at": created_at,
                            "status": status,
                            "inr_amount": float(inr_amount)
                        }

            except (TypeError, ValueError, KeyError) as e:
                print(f"Error processing order: {str(e)}")
                continue

        # Convert Decimal to float for JSON serialization
        for sym_data in analysis.values():
            sym_data["total_volume_inr"] = float(sym_data["total_volume_inr"])
            for side in ["buy_orders", "sell_orders"]:
                sym_data[side]["volume_inr"] = float(sym_data[side]["volume_inr"])
                sym_data[side]["avg_price"] = float(sym_data[side]["avg_price"])
                sym_data[side]["total_qty"] = float(sym_data[side]["total_qty"])

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