import logging
import time
import requests
from bity_arbitrage_bot.enums import Exchange


class ArbitrageBot:
    def __init__(self):
        self.symbols = ["BTC-BRL", "USDT-BRL", "ETH-BRL"]
        self.balance = {
            Exchange.BITPRECO: {"BTC": 1000, "USDT": 1000, "ETH": 1000, "BRL": 1000},
            Exchange.BINANCE: {"BTC": 1000, "USDT": 1000, "ETH": 1000, "BRL": 1000},
        }
        self.exchange_fee_percent = {Exchange.BITPRECO: 0.02, Exchange.BINANCE: 0.03}
        self.pnl = 0  # BRL
        self.trading_amount = 5  # BRL
        self.min_profit_percent = 0.05
        self.interval_ms = 100
        self.api_rate_limit = {
            Exchange.BITPRECO: {"max_req": 20, "window_time_ms": 100},
            Exchange.BINANCE: {"max_req": 20, "window_time_ms": 100},
        }
        self.exchanges_endpoints = {
            Exchange.BITPRECO: ["https://api.bitpreco.com"],
            Exchange.BINANCE: [
                "https://api.binance.com",
                "https://api-gcp.binance.com",
                "https://api1.binance.com",
                "https://api2.binance.com",
                "https://api3.binance.com",
                "https://api4.binance.com",
            ],
        }  # Not used, but could be used to request another endpoint in case of failure

    def check_balance(self) -> None:
        for exchange in [Exchange.BITPRECO, Exchange.BINANCE]:
            if self.balance[exchange]["BRL"] < self.trading_amount:
                msg = f"Insufficient BRL balance on exchange: {exchange}"
                logging.error(msg)
                raise Exception(msg)

    def check_api_rate_limit(self) -> None:
        REQS_PER_ARBITRAGE = 2
        max_exchange_interval_ms = 0
        for exchange in [Exchange.BITPRECO, Exchange.BINANCE]:
            exchange_interval = (
                self.api_rate_limit[exchange]["window_time_ms"]
                / self.api_rate_limit[exchange]["max_req"]
            )
            max_exchange_interval_ms = max(
                max_exchange_interval_ms, REQS_PER_ARBITRAGE * exchange_interval
            )

        self.interval_ms = max(self.interval_ms, max_exchange_interval_ms)

    def get_prices(self, symbol: str) -> tuple[float, float, float, float]:
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
                float(bitpreco_bid["price"]),
                float(bitpreco_ask["price"]),
                float(binance_bid[0]),
                float(binance_ask[0]),
            )

        except Exception as e:
            msg = f"Cannot get prices: {e}"
            logging.error(msg)
            raise Exception(msg)

    def calculate_real_prices(
        self, bid: float, ask: float, bid_fee: float, ask_fee: float
    ) -> tuple[float, float]:
        real_bid = bid * (1 + bid_fee)
        real_ask = ask * (1 - ask_fee)

        return real_bid, real_ask

    def check_arbitrage_opportunity(self, real_bid: float, real_ask: float) -> bool:
        profit_percent = real_ask / real_bid - 1

        return profit_percent >= self.min_profit_percent

    def make_transactions(
        self,
        symbol: str,
        exchange_to_buy: Exchange,
        real_ask: float,
        exchange_to_sell: Exchange,
        real_bid: float,
    ) -> None:
        buy_transaction = False
        sell_transaction = False

        try:
            logging.debug("ARBITRAGE OPPORTUNITY FOUNDED! MAKING TRANSATIONS...")

            crypto = symbol.split("-")[0]
            coin = symbol.split("-")[1]

            # Buy
            self.balance[exchange_to_buy][coin] -= self.trading_amount
            crypto_qty_added = self.trading_amount / real_ask
            self.balance[exchange_to_buy][crypto] += crypto_qty_added
            self.pnl -= self.trading_amount
            buy_transaction = True
            # Sell
            self.balance[exchange_to_sell][crypto] -= crypto_qty_added
            coin_qty_added = crypto_qty_added * real_bid
            self.balance[exchange_to_sell][coin] += coin_qty_added
            self.pnl += coin_qty_added
            sell_transaction = True

            logging.debug("ARBITRAGE SUCCESS!!!")
            logging.info(f"Updated P&L: {self.pnl}")

        except Exception as e:
            msg = f"Cannot make transactions: {e}"
            logging.error(msg)

            # In case the transactions were made using real API
            if buy_transaction and not sell_transaction:
                # Check if sell_transaction did not occurred
                # Try to make sell_transaction again
                pass

            raise Exception(msg)

    def wait_interval(self, elapsed_time_sec: float) -> None:
        wait_sec = max(self.interval_ms / 1000 - elapsed_time_sec, 0)
        time.sleep(wait_sec)

    def run(self) -> None:
        while True:
            for symbol in self.symbols:
                start_time = time.time()
                logging.debug(f"Checking arbitrage opportunity for: {symbol}")

                bitpreco_bid, bitpreco_ask, binance_bid, binance_ask = self.get_prices(
                    symbol=symbol
                )
                logging.debug(
                    f"{bitpreco_bid}, {bitpreco_ask}, {binance_bid}, {binance_ask}"
                )

                if bitpreco_bid and binance_ask:
                    real_bid, real_ask = self.calculate_real_prices(
                        bid=bitpreco_bid,
                        ask=binance_ask,
                        bid_fee=self.exchange_fee_percent[Exchange.BITPRECO],
                        ask_fee=self.exchange_fee_percent[Exchange.BINANCE],
                    )
                    is_arbitrage = self.check_arbitrage_opportunity(
                        real_bid=real_bid, real_ask=real_ask
                    )

                    if is_arbitrage:
                        self.make_transactions(
                            symbol=symbol,
                            exchange_to_buy=Exchange.BINANCE,
                            real_ask=real_ask,
                            exchange_to_sell=Exchange.BITPRECO,
                            real_bid=real_bid,
                        )
                elif binance_bid and bitpreco_ask:
                    real_bid, real_ask = self.calculate_real_prices(
                        bid=binance_bid,
                        ask=bitpreco_ask,
                        bid_fee=self.exchange_fee_percent[Exchange.BINANCE],
                        ask_fee=self.exchange_fee_percent[Exchange.BITPRECO],
                    )
                    is_arbitrage = self.check_arbitrage_opportunity(
                        real_bid=real_bid, real_ask=real_ask
                    )

                    if is_arbitrage:
                        self.make_transactions(
                            symbol=symbol,
                            exchange_to_buy=Exchange.BITPRECO,
                            real_ask=real_ask,
                            exchange_to_sell=Exchange.BINANCE,
                            real_bid=real_bid,
                        )

                self.wait_interval(elapsed_time_sec=time.time() - start_time)
