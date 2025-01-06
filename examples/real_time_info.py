import easykiwoom
import time

market = easykiwoom.Market()
market.initialize(logging_level='INFO')

stocks = ['005930', '000660', '035420', '035720', '051910']
market.register_price_info(stocks)
time.sleep(3)

for _ in range(10):
    for stock in stocks:
        price_info = market.get_price_info(stock, wait_time=3)
        print(f'{stock}: {price_info["현재가"]}')
    print('')
    time.sleep(1)

market.terminate()
