import requests


class ArbitrageBot:
    def __init__(self):
        self.symbols = ["BTC-BRL", "USDT-BRL", "ETH-BRL"]
        self.balance = {
            "bitpreco": {"BTC": 1000, "USDT": 1000, "ETH": 1000, "BRL": 1000},
            "binance": {"BTC": 1000, "USDT": 1000, "ETH": 1000, "BRL": 1000},
        }
        self.pnl = 0
        self.trading_amount = 5  # BRL
        self.min_profit_percent = 0.05

    def get_prices(self, symbol: str):
        try:
            bitpreco_req = requests.get(
                f"https://api.bitpreco.com/{symbol.lower()}/orderbook"
            )
            binance_req = requests.get(
                f"https://api.binance.com/api/v3/depth?symbol={symbol.replace("-", "")}"
            )

            bitpreco_req_json = bitpreco_req.json()
            binance_req_json = binance_req.json()

            bitpreco_bid = max(bitpreco_req_json["bids"], key=lambda x: x["price"])
            bitpreco_ask = min(bitpreco_req_json["asks"], key=lambda x: x["price"])
            binance_bid = max(binance_req_json["bids"], key=lambda x: x[0])
            binance_ask = min(binance_req_json["asks"], key=lambda x: x[0])

            return (
                bitpreco_bid["price"],
                bitpreco_ask["price"],
                binance_bid[0],
                binance_ask[0],
            )

        except Exception as e:
            raise Exception(f"Cannot get prices: {e}")
