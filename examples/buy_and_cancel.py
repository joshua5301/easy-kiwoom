import easykiwoom
import time

market = easykiwoom.Market()
market.initialize(logging_level='INFO')

stocks = ['005930', '000660', '035420', '035720', '051910']
order_numbers = []

market.register_price_info(stocks)

for stock in stocks:
    cur_price = market.get_price_info(stock)['현재가']
    order = {
        '구분': '매수',
        '주식코드': stock,
        '수량': 1,
        '가격': cur_price - 1000,
        '시장가': False
    }
    order_number = market.send_order(order)
    order_numbers.append(order_number)

time.sleep(10)

for stock, order_number in zip(stocks, order_numbers):
    order = {
        '구분': '매수취소',
        '주식코드': stock,
        '수량': 1,
        '원주문번호': order_number,
    }
    market.cancel_order(order)

market.terminate()