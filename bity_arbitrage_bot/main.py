import logging

from bity_arbitrage_bot.arbitrage_bot import ArbitrageBot

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [Bity Arbitrage BOT] %(levelname)s: %(message)s",
)

if __name__ == "__main__":
    arbitrage_bot = ArbitrageBot()
    arbitrage_bot.run()
