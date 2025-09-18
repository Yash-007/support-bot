import requests
from datetime import datetime
import argparse

CANDLESTICK_URL = "https://coinswitch.co/pro/api/v1/prograph/getDataForCandlestick"
TRADES_URL = "https://coinswitch.co/pro/api/v1/cspro/closed-orders"


class PortfolioAnalyzer:
    def __init__(self, auth_token, verify_ssl=True):
        self.session = requests.Session()
        self.session.cookies.set('st', auth_token)
        self.verify_ssl = verify_ssl

    def fetch_candlestick_data(self, symbol, from_time, to_time, c_duration, exchange):
        params = {
            "symbol": symbol,
            "from_time": from_time,
            "to_time": to_time,
            "c_duration": c_duration,
            "exchange": exchange,
        }
        resp = self.session.get(CANDLESTICK_URL, params=params, verify=self.verify_ssl)
        resp.raise_for_status()
        return resp.json()["result"]

    def fetch_trades(self, currency, from_date, to_date, page=1):
        trades = []
        currency = f'["{currency}"]'
        while True:
            resp = self.session.get(TRADES_URL, params={"page": page, "currency": currency, "from_date": from_date, "to_date": to_date}, verify=self.verify_ssl)
            resp.raise_for_status()
            data = resp.json()
            orders = data['data']['orders']
            if not orders:
                break
            trades.extend(orders)
            page += 1
        return trades

    def generate_portfolio_series(self, symbol: str, from_time: int, to_time: int, c_duration: int, exchange: str):
        candles = self.fetch_candlestick_data(symbol, from_time, to_time, c_duration, exchange)
    
        currncy = symbol.lower().replace("inr", ",inr")
        from_date = datetime.fromtimestamp(from_time / 1000).strftime('%Y-%m-%d')
        to_date = datetime.fromtimestamp(to_time / 1000).strftime('%Y-%m-%d')

        trades = self.fetch_trades(currncy, from_date, to_date)
        # Sort trades by time ascending
        def trade_ts(trade):
            # Convert ISO8601 to ms since epoch
            dt = datetime.fromisoformat(trade["created_at"].replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        trades = sorted(trades, key=trade_ts)

        cash = 0.0
        asset = 0.0
        trade_idx = 0
        series = []

        for candle in candles:
            ts = int(candle["close_time"])
            price = float(candle["c"])
            # Apply trades up to this timestamp
            while trade_idx < len(trades) and trade_ts(trades[trade_idx]) <= ts:
                t = trades[trade_idx]
                qty = float(t["executed_quantity"])
                avg_price = float(t["average_execution_price"])
                inr_amount = float(t.get("inr_amount", t.get("quote_amount", 0)))
                if t["trade_type"] == "buy":
                    asset += qty
                    cash -= inr_amount
                elif t["trade_type"] == "sell":
                    asset -= qty
                    cash += inr_amount
                trade_idx += 1
            asset_value = asset * price
            total = cash + asset_value
            series.append({
                "timestamp": ts,
                "cash": cash,
                "asset": asset,
                "asset_value": asset_value,
                "total": total,
            })
        return { "series": series, "candles": candles }
